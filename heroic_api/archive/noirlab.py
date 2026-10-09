"""Searches of the NOIRLab Astro Data Archive"""
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import ClassVar

from astroquery.noirlab import NOIRLabClass
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (SPECTRUM_BOX_HALF_WIDTH, ArchiveModes, ArchiveQuery, ArchiveSearch, MatchTypes,
                                        ReductionLevels, SearchResult, archive_codes, as_float, as_str, half_diagonal,
                                        search_result, union, within_field_of_view)
from heroic_api.models import Instrument

# NOIRLab imaging boxes are widened by this margin, since a raw file's center comes from its header pointing.
# Any noirlabs upper margin of pointing error is approximately this amount.
NOIRLAB_POINTING_MARGIN = 2 / 60  # degrees

NOIRLAB_FIELDS = [
    'md5sum', 'url', 'archive_filename', 'telescope', 'instrument', 'obs_type', 'proc_type', 'prod_type',
    'dateobs_center', 'ra_center', 'dec_center', 'release_date', 'ifilter', 'exposure', 'proposal', 'OBJECT'
]

# Radius in degrees of the smallest circle that holds each NOIRLab imager's field of view at any rotation
NOIRLAB_FIELD_RADII = {
    # DECam's field is round and 2.2 degrees across
    'decam': 1.1,
    'newfirm': half_diagonal(28, 28),
    # Goodman's imaging field is round and 7.2' across
    'ghts_red_imager': 3.6 / 60,
    'ghts_blue_imager': 3.6 / 60,
    'goodman': 3.6 / 60,
    'sami': half_diagonal(3.1, 3.1),
    'spartan': half_diagonal(5.04, 5.04),
}

# proc_type values that count as processed data for each NOIRLab instrument. Instruments not listed here,
# such as SOAR's, only have raw data at NOIRLab. Searches always name the proc_type values they want, since
# NOIRLab rejects searches on header fields such as OBJECT without them, and every extra value slows those down.
NOIRLAB_PROCESSED_TYPES = {
    'decam': ('instcal',),
    # NOIRLab's processed NEWFIRM data from Blanco is stacked rather than per exposure
    'newfirm': ('instcal', 'stacked'),
}

# Until March 2024, NOIRLab filed the raw files of both of Goodman's cameras, in both modes, under this one code.
# We have to examine specific header items to divine if these files were blue/red and imager/spectrograph.
# INSTCONF names the camera from January 2017. Older files don't, but files from
# before the red camera's first frame are all from the blue camera, and later files that don't name their camera are
# given the red camera by default. A GRATING header of no grating means an image.
NOIRLAB_GOODMAN_CODE = 'goodman'
NOIRLAB_GOODMAN_FIELDS = ['INSTCONF', 'GRATING']
NOIRLAB_GOODMAN_CODES = {
    ('red', ArchiveModes.IMAGING): 'ghts_red_imager',
    ('red', ArchiveModes.SPECTROSCOPY): 'ghts_red',
    ('blue', ArchiveModes.IMAGING): 'ghts_blue_imager',
    ('blue', ArchiveModes.SPECTROSCOPY): 'ghts_blue',
}
GOODMAN_RED_CAMERA_START = datetime(2016, 10, 13, tzinfo=dt_timezone.utc)
# Need a regex for this since they have used multiple different versions over the years
GOODMAN_NO_GRATING = re.compile(r'<?no[ _]grating>?', re.IGNORECASE)


@dataclass(frozen=True)
class NoirlabSearch(ArchiveSearch):
    """A search of the NOIRLab Astro Data Archive.

    NOIRLab only records each file's center, so every match is approximate. Imaging searches select centers
    in a box around the position as wide as the widest field of view searched, plus a margin, then keep the
    files whose instrument's field of view contains the position. Spectrum searches select recorded positions
    within +/-40" of the position to approximate the slit and pointing error.
    """
    archive: ClassVar[str] = 'noirlab'
    archive_name: ClassVar[str] = _('NOIRLab Astro Data Archive')
    telescopes: tuple
    instruments: tuple

    @property
    def match(self) -> str:
        return MatchTypes.APPROXIMATE

    @classmethod
    def combine(cls, searches: list) -> 'NoirlabSearch':
        return cls(
            searches[0].mode,
            telescopes=union(search.telescopes for search in searches),
            instruments=union(search.instruments for search in searches),
        )

    def covers(self, frame: dict) -> bool:
        return frame['telescope'] in self.telescopes and frame['instrument'] in self.instruments

    def run(self, query: ArchiveQuery) -> SearchResult:
        processed_types = union(NOIRLAB_PROCESSED_TYPES.get(instrument, ()) for instrument in self.instruments)
        proc_types = {
            ReductionLevels.RAW: ('raw',),
            ReductionLevels.PROCESSED: processed_types,
            ReductionLevels.ALL: ('raw', *processed_types),
        }[query.reduction_level]
        if not proc_types:
            # Processed data was asked for from instruments that only have raw data
            return SearchResult(frames=[], truncated=False)
        instruments = list(self.instruments)
        outfields = NOIRLAB_FIELDS
        if NOIRLAB_GOODMAN_CODE in instruments:
            # NOIRLab only accepts header fields that the files of the first instrument and proc_type have. Goodman's
            # old code goes first, since only its files have the fields that attribute them, and they're all raw.
            # A search for processed files leaves it out, since NOIRLab rejects the search otherwise.
            instruments.remove(NOIRLAB_GOODMAN_CODE)
            if 'raw' in proc_types:
                instruments.insert(0, NOIRLAB_GOODMAN_CODE)
                outfields = NOIRLAB_FIELDS + NOIRLAB_GOODMAN_FIELDS
        client = NOIRLabClass()
        client.TIMEOUT = settings.ARCHIVE_QUERY_TIMEOUT
        filters = [
            ['dateobs_center', query.start.isoformat(), query.end.isoformat()],
            # Unreleased files have a future release date, so this keeps public files only
            ['release_date', '1900-01-01', timezone.now().date().isoformat()],
            ['telescope', *self.telescopes],
            ['instrument', *instruments],
            ['obs_type', 'object'],
            ['proc_type', *proc_types],
        ]
        if self.mode == ArchiveModes.IMAGING:
            filters.append(['prod_type', 'image'])

        if query.target_name:
            # Matches the OBJECT header the observer set, ignoring case
            searches = [[['OBJECT', query.target_name, 'iexact']]]
        else:
            half_width = SPECTRUM_BOX_HALF_WIDTH
            if self.mode == ArchiveModes.IMAGING:
                half_width = max(NOIRLAB_FIELD_RADII[instrument] for instrument in self.instruments)
                half_width += NOIRLAB_POINTING_MARGIN
            searches = _center_box_terms(query.ra, query.dec, half_width)

        frames = []
        truncated = False
        for terms in searches:
            # Asking for one more file than the limit shows whether the archive holds more
            table = client.query_metadata(
                {'outfields': outfields, 'search': terms + filters},
                sort='-dateobs_center', limit=query.row_limit + 1, cache=False
            )
            truncated = truncated or len(table) > query.row_limit
            # Goodman's old code finds files from both cameras and modes, and some that can't be attributed
            frames.extend(frame for frame in map(self._frame, table) if self.covers(frame))
        if self.mode == ArchiveModes.IMAGING and not query.target_name:
            # The box is wider than each field at its corners, in RA towards the poles, and for narrower fields
            frames = within_field_of_view(frames, query.coordinate, NOIRLAB_FIELD_RADII, NOIRLAB_POINTING_MARGIN)
        return search_result(frames, query.row_limit, truncated)

    @staticmethod
    def _frame(row) -> dict:
        proc_type = as_str(row['proc_type'])
        archive_filename = as_str(row['archive_filename'])
        observation_date = parse_datetime(row['dateobs_center'])
        instrument = as_str(row['instrument'])
        if instrument == NOIRLAB_GOODMAN_CODE:
            instrument = _goodman_code(row, observation_date)
        return {
            'id': as_str(row['md5sum']),
            # The archive filename is the file's full path on the archive's servers
            'filename': os.path.basename(archive_filename) if archive_filename else None,
            'url': as_str(row['url']),
            'observation_date': observation_date,
            'ra': as_float(row['ra_center']),
            'dec': as_float(row['dec_center']),
            'target_name': as_str(row['OBJECT']),
            'telescope': as_str(row['telescope']),
            'instrument': instrument,
            'filter': as_str(row['ifilter']),
            'exposure_time': as_float(row['exposure']),
            'observation_type': as_str(row['obs_type']),
            'reduction_level': proc_type,
            'processed': proc_type not in (None, 'raw'),
            'proposal_id': as_str(row['proposal']),
            # NOIRLab gives the release date without a time or time zone
            'public_date': parse_datetime(row['release_date']).replace(tzinfo=dt_timezone.utc),
        }


def _goodman_code(row, observation_date: datetime):
    """The current code for the Goodman camera and mode that took a file filed under Goodman's old code

    Returns None if the file doesn't say whether it's an image or a spectrum, so no search covers it.
    """
    camera = (as_str(row['INSTCONF']) or '').lower()
    if camera not in ('red', 'blue'):
        camera = 'blue' if observation_date < GOODMAN_RED_CAMERA_START else 'red'
    grating = as_str(row['GRATING'])
    if not grating:
        return None
    mode = ArchiveModes.IMAGING if GOODMAN_NO_GRATING.fullmatch(grating) else ArchiveModes.SPECTROSCOPY
    return NOIRLAB_GOODMAN_CODES.get((camera, mode))


def _center_box_terms(ra: float, dec: float, half_width: float) -> list:
    """NOIRLab search terms selecting file centers within half_width degrees (on the sky) of ra, dec

    Returns a list of search term lists: one normally, or two when the box crosses RA 0/360, since terms
    are ANDed and a range cannot wrap. RA is scaled at the poleward edge of the box, so it errs on the
    wide side.
    """
    dec_lo, dec_hi = max(dec - half_width, -90.0), min(dec + half_width, 90.0)
    dec_term = ['dec_center', dec_lo, dec_hi]
    if dec_lo == -90.0 or dec_hi == 90.0:
        # The box reaches a pole, so it covers every RA
        return [[dec_term]]
    ra_half_width = half_width / math.cos(math.radians(max(abs(dec_lo), abs(dec_hi))))
    if ra_half_width >= 180:
        return [[dec_term]]
    lo, hi = ra - ra_half_width, ra + ra_half_width
    if lo < 0:
        ranges = [(0.0, hi), (lo + 360, 360.0)]
    elif hi > 360:
        ranges = [(lo, 360.0), (0.0, hi - 360)]
    else:
        ranges = [(lo, hi)]
    return [[['ra_center', range_lo, range_hi], dec_term] for range_lo, range_hi in ranges]


def noirlab_searches(instrument) -> list:
    """Archive searches for an instrument on a telescope whose data is at NOIRLab

    The searches use the archive ids of the instrument and its telescope, one for each mode the instrument supports.
    NOIRLab files a camera's images and spectra under different codes, such as Goodman's, so an imaging search uses
    the instrument's codes in NOIRLAB_FIELD_RADII, which sizes its box, while a spectroscopy search uses the other
    instrument codes. Goodman's old code has both images and spectra, so both searches use it.
    """
    telescope_id = instrument.telescope.archive_id
    codes = archive_codes(instrument)
    if not telescope_id or not codes:
        return []
    imager_codes = tuple(code for code in codes if code in NOIRLAB_FIELD_RADII)
    spectrograph_codes = tuple(code for code in codes
                               if code not in NOIRLAB_FIELD_RADII or code == NOIRLAB_GOODMAN_CODE)
    searches = []
    if Instrument.SupportedModes.IMAGER in instrument.supported_modes and imager_codes:
        searches.append(NoirlabSearch(ArchiveModes.IMAGING, (telescope_id,), imager_codes))
    if Instrument.SupportedModes.SPECTROGRAPH in instrument.supported_modes and spectrograph_codes:
        searches.append(NoirlabSearch(ArchiveModes.SPECTROSCOPY, (telescope_id,), spectrograph_codes))
    return searches
