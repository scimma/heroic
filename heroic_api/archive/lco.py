"""Searches of the LCO Science Archive"""
import logging
import warnings
from dataclasses import dataclass
from typing import ClassVar

from astroquery.exceptions import MaxResultsWarning, NoResultsWarning
from astroquery.lco import LcoArchiveClass
from django.conf import settings

from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (ArchiveModes, ArchiveQuery, ArchiveSearch, ReductionLevels,
                                        SearchResult, archive_codes, as_float, as_str, search_result, union)
from heroic_api.models import Instrument

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


@dataclass(frozen=True)
class LcoSearch(ArchiveSearch):
    """A search of the LCO Science Archive.

    The archive returns the frames whose footprint contains the position, so imaging matches are exact. A spectrum's
    footprint is its slit with some padding, so spectroscopy matches are approximate, with false positives but not
    false negatives.

    A search finds the frames from its cameras on its telescope at its sites. The archive takes one site and one
    camera per query, so a search of several leaves them out of the query and keeps the matching frames afterwards.
    """
    archive: ClassVar[str] = 'lco'
    archive_name: ClassVar[str] = _('LCO Science Archive')
    sites: tuple
    # The archive's code for the telescope, i.e. '1m0a', '2m0a', 'igla', etc.
    telescope: str = ''
    cameras: tuple = ()

    @classmethod
    def combine(cls, searches: list) -> 'LcoSearch':
        telescopes = {search.telescope for search in searches}
        cameras = {search.cameras for search in searches}
        return cls(
            searches[0].mode,
            sites=union(search.sites for search in searches),
            # A telescope or camera filter is kept only if every search has the same one
            telescope=telescopes.pop() if len(telescopes) == 1 else '',
            cameras=cameras.pop() if len(cameras) == 1 else (),
        )

    def covers(self, frame: dict) -> bool:
        # _frame names the telescope as the site and telescope code, e.g. 'tfn.1m0a'
        site, _, telescope = (frame['telescope'] or '').partition('.')
        return (site in self.sites and self.telescope in ('', telescope)
                and (not self.cameras or frame['instrument'] in self.cameras))

    def run(self, query: ArchiveQuery) -> SearchResult:
        client = LcoArchiveClass()
        client.TIMEOUT = settings.ARCHIVE_QUERY_TIMEOUT
        criteria = {
            'start': query.start,
            'end': query.end,
            'site_id': self.sites[0] if len(self.sites) == 1 else None,
            'telescope_id': self.telescope or None,
            'instrument_id': self.cameras[0] if len(self.cameras) == 1 else None,
            'include_configuration_type': LCO_CONFIGURATION_TYPES[self.mode],
        }
        if query.reduction_level != ReductionLevels.ALL:
            criteria['processed'] = query.reduction_level == ReductionLevels.PROCESSED
        if settings.LCO_ARCHIVE_TOKEN:
            # Logged in searches get 1000 frames per request instead of 100
            client.login(token=settings.LCO_ARCHIVE_TOKEN)
            if not client.authenticated():
                logger.warning('The LCO archive rejected LCO_ARCHIVE_TOKEN, so searching it anonymously')
        # Asking for one more frame than the limit shows whether the archive holds more
        options = {'row_limit': query.row_limit + 1, 'show_progress': False, 'cache': False}
        if query.target_name:
            table = client.query_criteria(target_name_iexact=query.target_name, **options, **criteria)
        else:
            table = client.query_region(query.coordinate, **options, **criteria)
        frames = [frame for frame in map(self._frame, table) if self.covers(frame)]
        return search_result(frames, query.row_limit, truncated=len(table) > query.row_limit)

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


def lco_searches(instrument) -> list:
    """Archive searches for an instrument on one of LCO's telescopes

    An instrument's archive ids are the codes of its cameras, such as MuSCAT's four, and its telescope's archive id
    is the archive's code for the telescope. Each search finds the frames from those cameras on that telescope at
    the instrument's site, so each frame matches one instrument. NRES units are listed under their own enclosures,
    which is where the archive files their frames, apart from copies of the raw frames under a placeholder telescope.
    """
    cameras = archive_codes(instrument)
    if not cameras:
        return []
    telescope = instrument.telescope
    # LCO's HEROIC site ids end with the archive's site code, e.g. 'lco.coj'
    site = telescope.site_id.rsplit('.', 1)[-1]
    searches = []
    if Instrument.SupportedModes.IMAGER in instrument.supported_modes:
        searches.append(LcoSearch(ArchiveModes.IMAGING, (site,), telescope=telescope.archive_id, cameras=cameras))
    if Instrument.SupportedModes.SPECTROGRAPH in instrument.supported_modes:
        searches.append(LcoSearch(ArchiveModes.SPECTROSCOPY, (site,), telescope=telescope.archive_id, cameras=cameras))
    return searches
