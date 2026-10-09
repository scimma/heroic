"""Searches of the Gemini Observatory Archive"""
from dataclasses import dataclass
from datetime import timezone as dt_timezone
from typing import ClassVar

import astropy.units as u
from astroquery.gemini import ObservationsClass as GeminiObservationsClass
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (SPECTRUM_BOX_HALF_WIDTH, ArchiveModes, ArchiveQuery, ArchiveSearch, MatchTypes,
                                        ReductionLevels, SearchResult, archive_codes, as_float, as_str, half_diagonal,
                                        search_result, union, within_field_of_view)
from heroic_api.models import Instrument

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


@dataclass(frozen=True)
class GeminiSearch(ArchiveSearch):
    """A search of the Gemini Observatory Archive.

    Gemini matches each frame's recorded position against a box around the position, whose half-width is the
    search radius, so every match is approximate. Imaging searches send the radius of the circle that holds the
    instrument's field of view at any rotation, then keep the frames within that distance. Spectrum searches use
    a radius of 40". The archive takes one instrument per query, so a search of several instruments leaves the
    instrument out, sends the widest field's radius, and keeps the frames of its own instruments.
    """
    archive: ClassVar[str] = 'gemini'
    archive_name: ClassVar[str] = _('Gemini Observatory Archive')
    telescopes: tuple
    instruments: tuple

    @property
    def match(self) -> str:
        return MatchTypes.APPROXIMATE

    @classmethod
    def combine(cls, searches: list) -> 'GeminiSearch':
        return cls(
            searches[0].mode,
            telescopes=union(search.telescopes for search in searches),
            instruments=union(search.instruments for search in searches),
        )

    def covers(self, frame: dict) -> bool:
        instrument = (frame['instrument'] or '').upper()
        # Some frames have no telescope recorded, but their instrument is only on one telescope
        telescope_matches = frame['telescope'] is None or frame['telescope'] in self.telescopes
        return telescope_matches and instrument in {own.upper() for own in self.instruments}

    def run(self, query: ArchiveQuery) -> SearchResult:
        client = GeminiObservationsClass()
        several_instruments = len(self.instruments) > 1
        # Gemini has two telescopes, so a search of both leaves the telescope out
        terms = [self.telescopes[0]] if len(self.telescopes) == 1 else []
        if not several_instruments:
            terms.append(self.instruments[0])
        # The date term selects whole UT days, both ends included. The archive has a bug taking datetime
        # ranges, intermittently fails with a 502 error when exactly one end is at midnight.
        # Specifying 'science' and 'OBJECT' drop calibrations and acquisitions.
        terms += [GEMINI_MODES[self.mode], 'science', 'OBJECT', f'{query.start:%Y%m%d}-{query.end:%Y%m%d}']
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
            if self.mode == ArchiveModes.IMAGING:
                # Use the max half diagnol for any instruments we are searching for to make sure we contain the point
                # We will post-filter down the frames after retrieving them before passing them on to the user.
                half_width = max(GEMINI_FIELD_RADII[instrument] for instrument in self.instruments)
            else:
                half_width = SPECTRUM_BOX_HALF_WIDTH
            options['radius'] = half_width * u.deg
        table = client.query_raw(*terms, **options)

        instruments = {instrument.upper() for instrument in self.instruments}
        now = timezone.now()
        frames = []
        # Now post-process the frames retrieved to make sure they fit the query params
        for row in table:
            # A multi-object spectrum records its mask's field center rather than the slits, so ignore it.
            if not query.target_name and as_str(row['mode']) == 'MOS':
                continue
            frame = self._frame(row)
            # If we specified by instrument, ignore instruments retrieved that weren't asked for
            if several_instruments and (frame['instrument'] or '').upper() not in instruments:
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
        if self.mode == ArchiveModes.IMAGING and not query.target_name:
            # Do another FOV check since our query errs on the side of having false positives
            frames = within_field_of_view(frames, query.coordinate, GEMINI_FIELD_RADII)
        return search_result(frames, query.row_limit, truncated=len(table) >= GEMINI_ROW_CAP)

    def _frame(self, row) -> dict:
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
            'telescope': as_str(row['telescope']) or (self.telescopes[0] if len(self.telescopes) == 1 else None),
            'instrument': as_str(row['instrument']) or (self.instruments[0] if len(self.instruments) == 1 else None),
            'filter': as_str(row['filter_name']),
            'exposure_time': as_float(row['exposure_time']),
            'observation_type': as_str(row['observation_type']),
            'reduction_level': reduction,
            'processed': reduction not in (None, 'RAW'),
            'proposal_id': as_str(row['program_id']),
            'public_date': parse_datetime(release).replace(tzinfo=dt_timezone.utc) if release else None,
        }


def gemini_searches(instrument) -> list:
    """Archive searches for an instrument on a telescope whose data is at Gemini

    The searches use the archive ids of the instrument and its telescope, one for each mode the instrument supports.
    Gemini files a camera's images and spectra under the same code, so a spectroscopy search uses all of the
    instrument's codes, and an imaging search uses those in GEMINI_FIELD_RADII, which sizes its box.
    """
    telescope_id = instrument.telescope.archive_id
    codes = archive_codes(instrument)
    if not telescope_id or not codes:
        return []
    imager_codes = tuple(code for code in codes if code in GEMINI_FIELD_RADII)
    searches = []
    if Instrument.SupportedModes.IMAGER in instrument.supported_modes and imager_codes:
        searches.append(GeminiSearch(ArchiveModes.IMAGING, (telescope_id,), imager_codes))
    if Instrument.SupportedModes.SPECTROGRAPH in instrument.supported_modes:
        searches.append(GeminiSearch(ArchiveModes.SPECTROSCOPY, (telescope_id,), codes))
    return searches
