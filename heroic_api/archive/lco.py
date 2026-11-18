"""Searches of the LCO Science Archive"""
import logging
import warnings

from astroquery.exceptions import MaxResultsWarning, NoResultsWarning
from astroquery.lco import LcoArchiveClass
from django.conf import settings

from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (Archive, ArchiveModes, ArchiveQuery, ArchiveSearch, ReductionLevels,
                                        SearchResult, archive_codes, as_float, as_str)

logger = logging.getLogger(__name__)

# The LCO astroquery module reports empty and truncated results as warnings. The searches below detect both
# conditions themselves, so the warnings would only add noise to the server logs.
warnings.filterwarnings('ignore', category=NoResultsWarning, module='astroquery')
warnings.filterwarnings('ignore', category=MaxResultsWarning, module='astroquery')

# The configuration types of science frames in each mode. FLOYDS spectra are SPECTRUM, and NRES spectra are TARGET.
LCO_CONFIGURATION_TYPES = {
    ArchiveModes.IMAGING: ('EXPOSE',),
    ArchiveModes.SPECTROSCOPY: ('SPECTRUM', 'TARGET'),
}


class LcoArchive(Archive):
    """The LCO Science Archive.

    The archive returns the frames whose footprint contains the position, so imaging matches are exact. A spectrum's
    footprint is its slit with some padding, so spectroscopy matches are approximate, with false positives but not
    false negatives.

    If there are any instruments selected, then this will make one query per instrument id. Otherwise it will make
    one query for all instruments together.
    """
    id = 'lco'
    name = _('LCO Science Archive')

    def instrument_keys(self, instrument, mode: str) -> list:
        """An instrument's archive ids are the codes of its cameras, such as MuSCAT's four, and its telescope's archive
        id is the archive's code for the telescope, such as '1m0a'. NRES units are listed under thier telescope code of
        'igla'.
        """
        # LCO's HEROIC site ids end with the archive's site code, e.g. 'lco.coj'
        site = instrument.telescope.site_id.rsplit('.', 1)[-1]
        return [(site, instrument.telescope.archive_id, camera) for camera in archive_codes(instrument)]

    def frame_key(self, frame: dict):
        # _frame names the telescope as the site and telescope code, e.g. 'tfn.1m0a'
        site, _, telescope = frame['telescope'].partition('.')
        return (site, telescope, frame['instrument'])

    def fetch(self, query: ArchiveQuery, search: ArchiveSearch) -> SearchResult:
        client = LcoArchiveClass()
        client.TIMEOUT = settings.ARCHIVE_QUERY_TIMEOUT
        criteria = {
            'start': query.start,
            'end': query.end,
            'include_configuration_type': LCO_CONFIGURATION_TYPES[search.mode],
        }
        if query.reduction_level != ReductionLevels.ALL:
            criteria['processed'] = query.reduction_level == ReductionLevels.PROCESSED
        if settings.LCO_ARCHIVE_TOKEN:
            # Logged in searches get 1000 frames per request instead of 100
            client.login(token=settings.LCO_ARCHIVE_TOKEN)
            if not client.authenticated():
                logger.warning('The LCO archive rejected LCO_ARCHIVE_TOKEN, so searching it anonymously')

        # If we have specific instruments selected, then set up the query params per instrument here
        narrowings = [{}]
        if not search.complete:
            narrowings = []
            for instrument in search.instruments:
                keys = self.instrument_keys(instrument, search.mode)
                site, telescope, camera = keys[0]
                # Instruments with multiple ids, i.e. multiple cameras, must leave the instrument id out
                narrowings.append({'site_id': site, 'telescope_id': telescope or None,
                                   'instrument_id': camera if len(keys) == 1 else None})

        # Asking for one more frame than the limit shows whether the archive holds more
        options = {'row_limit': query.row_limit + 1, 'show_progress': False, 'cache': False}
        frames = []
        truncated = False
        for narrowing in narrowings:
            if query.target_name:
                table = client.query_criteria(target_name_iexact=query.target_name, **options, **criteria, **narrowing)
            else:
                table = client.query_region(query.coordinate, **options, **criteria, **narrowing)
            truncated = truncated or len(table) > query.row_limit
            # The archive returns the newest frames first
            for frame in map(self._frame, table[:query.row_limit]):
                # The archive files each raw NRES spectrum twice, so this ignores the non-igla version
                if frame['observation_type'] == 'TARGET' and self.frame_key(frame)[1] != 'igla':
                    continue
                frames.append(frame)
        return SearchResult(frames, truncated)

    @staticmethod
    def _frame(row) -> dict:
        level = row['reduction_level']
        return {
            'id': as_str(row['id']),
            'filename': as_str(row['filename']),
            # The archive presigns this link, and it expires after 48 hours
            'url': as_str(row['url']),
            'observation_date': parse_datetime(row['observation_date']),
            # The center of the frame's footprint
            'ra': as_float(row['ra']),
            'dec': as_float(row['dec']),
            'target_name': as_str(row['target_name']),
            'telescope': '.'.join(part for part in (as_str(row['site_id']), as_str(row['telescope_id'])) if part),
            'instrument': as_str(row['instrument_id']),
            'filter': as_str(row['primary_optical_element']),
            'exposure_time': as_float(row['exposure_time']),
            'observation_type': as_str(row['configuration_type']),
            'reduction_level': str(level),
            'processed': level != 0,
            'proposal_id': as_str(row['proposal_id']),
            'public_date': parse_datetime(row['public_date']),
        }
