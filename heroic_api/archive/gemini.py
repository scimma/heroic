"""Searches of the Gemini Observatory Archive"""
from datetime import timezone as dt_timezone

import astropy.units as u
from astroquery.gemini import ObservationsClass as GeminiObservationsClass
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (SPECTRUM_BOX_HALF_WIDTH, Archive, ArchiveModes, ArchiveQuery, ArchiveSearch,
                                        MatchTypes, ReductionLevels, SearchResult, archive_codes, as_float, as_str,
                                        half_diagonal, union, within_field_of_view)

# Radius in degrees of the smallest circle that holds each Gemini imager's field of view at any rotation
# TODO: Fill in `footprint` for instruments and use that to get half_diagnol.
GEMINI_FIELD_RADII = {
    'GMOS-N': half_diagonal(5.5, 5.5),
    'GMOS-S': half_diagonal(5.5, 5.5),
    # F2's imaging field is round and 6.1' across
    'F2': 6.1 / 2 / 60,
    'GSAOI': half_diagonal(85 / 60, 85 / 60),
    # 'Alopeke and Zorro cover 60" in their wide-field mode, and 6.7" in their speckle mode
    'ALOPEKE': half_diagonal(1, 1),
    'ZORRO': half_diagonal(1, 1),
}

# The Gemini archive stops at this many rows without saying so, and has no row limit parameter.
GEMINI_ROW_CAP = 2000
GEMINI_FILE_URL = 'https://archive.gemini.edu/file/{}'
GEMINI_MODES = {ArchiveModes.IMAGING: 'imaging', ArchiveModes.SPECTROSCOPY: 'spectroscopy'}
GEMINI_REDUCTIONS = {ReductionLevels.RAW: 'RAW', ReductionLevels.PROCESSED: 'PROCESSED_SCIENCE'}


class GeminiArchive(Archive):
    """The Gemini Observatory Archive.

    Gemini matches each frame's recorded position against a box around the position, whose half-width is the
    search radius, so every match is approximate. Imaging searches send the radius of the circle that holds the
    widest field of view searched at any rotation, then keep the frames within their own instrument's field, so
    imaging frames are only found from instruments whose field of view is known. Spectrum searches use a radius
    of 40". The archive takes one instrument per query, so a search of several leaves the instrument out and finds
    every instrument's frames, keeping the others' only when it's a search of all of the archive's instruments.
    """
    id = 'gemini'
    name = _('Gemini Observatory Archive')

    def match(self, mode: str) -> str:
        return MatchTypes.APPROXIMATE

    def instrument_keys(self, instrument, mode: str) -> list:
        """The keys are the instrument's codes, since each is on one telescope, and some frames have no telescope
        recorded. Gemini files a camera's images and spectra under the same code, so spectroscopy uses all of the
        instrument's codes, and imaging uses those in GEMINI_FIELD_RADII, which sizes its box.
        """
        if not instrument.telescope.archive_id:
            return []
        codes = archive_codes(instrument)
        if mode == ArchiveModes.IMAGING:
            codes = [code for code in codes if code in GEMINI_FIELD_RADII]
        return [code.upper() for code in codes]

    def frame_key(self, frame: dict):
        return (frame['instrument'] or '').upper()

    def fetch(self, query: ArchiveQuery, search: ArchiveSearch) -> SearchResult:
        client = GeminiObservationsClass()
        telescopes = sorted({instrument.telescope.archive_id for instrument in search.instruments})
        codes = union(self.instrument_keys(instrument, search.mode) for instrument in search.instruments)
        # Gemini has two telescopes, so a search of both leaves the telescope out
        terms = [telescopes[0]] if len(telescopes) == 1 else []
        if len(codes) == 1:
            terms.append(codes[0])
        # The date term selects whole UT days, both ends included. The archive has a bug taking datetime
        # ranges, intermittently fails with a 502 error when exactly one end is at midnight.
        # Specifying 'science' and 'OBJECT' drop calibrations and acquisitions.
        terms += [GEMINI_MODES[search.mode], 'science', 'OBJECT', f'{query.start:%Y%m%d}-{query.end:%Y%m%d}']
        # The archive takes one reduction level per query, so a search of all of them leaves it out and keeps the raw
        # and processed frames afterwards, leaving out intermediate products such as PREPARED
        if query.reduction_level != ReductionLevels.ALL:
            terms.append(GEMINI_REDUCTIONS[query.reduction_level])
        options = {'orderby': 'ut_datetime_desc'}
        if query.target_name:
            # Matches the OBJECT header the observer set, ignoring case.
            options['object'] = query.target_name
        else:
            options['coordinates'] = query.coordinate
            if search.mode == ArchiveModes.IMAGING:
                # Use the max half diagnol for any instruments we are searching for to make sure we contain the point
                # We will post-filter down the frames after retrieving them before passing them on to the user.
                half_width = max(GEMINI_FIELD_RADII[code] for code in codes)
            else:
                half_width = SPECTRUM_BOX_HALF_WIDTH
            options['radius'] = half_width * u.deg
        table = client.query_raw(*terms, **options)

        now = timezone.now()
        frames = []
        # Now post-process the frames retrieved to make sure they fit the query params
        for row in table:
            # A multi-object spectrum records its mask's field center rather than the slits, so ignore it.
            if not query.target_name and as_str(row['mode']) == 'MOS':
                continue
            frame = self._frame(row, telescopes, codes)
            # A query without instrument filters finds every instrument's frames, including those not in HEROIC
            if not search.complete and self.frame_key(frame) not in codes:
                continue
            # Ignore reduction levels other than raw and processed science
            if frame['reduction_level'] not in GEMINI_REDUCTIONS.values():
                continue
            # The archive has no public-only filter, and the date term covers whole days
            public = frame['public_date'] is not None and frame['public_date'] <= now
            observed = frame['observation_date'] is not None and query.start <= frame['observation_date'] <= query.end
            # Only add the frame to results if it's public and was observed in the query's time range
            if public and observed:
                frames.append(frame)
        if search.mode == ArchiveModes.IMAGING and not query.target_name:
            # Do another FOV check since our query errs on the side of having false positives
            frames = within_field_of_view(frames, query.coordinate, GEMINI_FIELD_RADII)
        # The archive has no row limit parameter, and returns the newest frames first
        truncated = len(table) >= GEMINI_ROW_CAP or len(frames) > query.row_limit
        return SearchResult(frames[:query.row_limit], truncated)

    @staticmethod
    def _frame(row, telescopes: list, codes: tuple) -> dict:
        filename = as_str(row['filename'])
        reduction = as_str(row['reduction'])
        # Gemini gives UTC times and dates without a time zone, and some frames are missing them
        observed = as_str(row['ut_datetime'])
        release = as_str(row['release'])
        return {
            'id': as_str(row['data_label']),
            'filename': filename,
            'url': GEMINI_FILE_URL.format(filename) if filename else None,
            'observation_date': parse_datetime(observed).replace(tzinfo=dt_timezone.utc) if observed else None,
            'ra': as_float(row['ra']),
            'dec': as_float(row['dec']),
            'target_name': as_str(row['object']),
            # A frame missing its telescope or instrument has the one given in the query if present
            'telescope': as_str(row['telescope']) or (telescopes[0] if len(telescopes) == 1 else None),
            'instrument': as_str(row['instrument']) or (codes[0] if len(codes) == 1 else None),
            'filter': as_str(row['filter_name']),
            'exposure_time': as_float(row['exposure_time']),
            'observation_type': as_str(row['observation_type']),
            'reduction_level': reduction,
            'processed': reduction not in (None, 'RAW'),
            'proposal_id': as_str(row['program_id']),
            'public_date': parse_datetime(release).replace(tzinfo=dt_timezone.utc) if release else None,
        }
