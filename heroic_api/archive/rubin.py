"""Searches of the Rubin pointings that HEROIC stores from the Rubin schedule"""
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _

from heroic_api.archive.archive import (Archive, ArchiveModes, ArchiveQuery, ArchiveSearch, ReductionLevels,
                                        SearchResult, as_float, as_str)
from heroic_api.models import TelescopePointing
from heroic_api.tasks import RUBIN_INSTRUMENT_ID, RUBIN_TELESCOPE_ID


class RubinArchive(Archive):
    """The Rubin pointings HEROIC stores, rather than an external archive.

    Only performed pointings are searched, not planned ones. A pointing matches a position when its field of view
    contains it, so matches are exact. HEROIC has no files for the pointings, so frames have no filename or link,
    and searches for processed frames find none.
    """
    id = 'rubin'
    name = _('Rubin pointings stored in HEROIC')
    runs_locally = True

    def instrument_keys(self, instrument, mode: str) -> list:
        if instrument.id != RUBIN_INSTRUMENT_ID or mode != ArchiveModes.IMAGING:
            return []
        return [instrument.id]

    def frame_key(self, frame: dict):
        return frame['instrument']

    def fetch(self, query: ArchiveQuery, search: ArchiveSearch) -> SearchResult:
        if query.reduction_level == ReductionLevels.PROCESSED:
            return SearchResult(frames=[], truncated=False)
        pointings = TelescopePointing.objects.filter(
            telescope__id=RUBIN_TELESCOPE_ID, instrument__id=RUBIN_INSTRUMENT_ID, planned=False,
            date__gte=query.start, date__lte=query.end,
        )
        if query.target_name:
            pointings = pointings.filter(target__iexact=query.target_name)
        else:
            pointings = pointings.filter(field__contains=Point(query.ra, query.dec, srid=4326))
        # Asking for one more pointing than the limit shows whether there are more
        pointings = list(pointings.order_by('-date')[:query.row_limit + 1])
        return SearchResult([self._frame(pointing) for pointing in pointings[:query.row_limit]],
                            truncated=len(pointings) > query.row_limit)

    @staticmethod
    def _frame(pointing: TelescopePointing) -> dict:
        extra = pointing.extra or {}
        return {
            # Rubin's observation id, or HEROIC's id for pointings stored without one
            'id': as_str(extra.get('obs_id')) or str(pointing.id),
            'filename': None,
            'url': None,
            'observation_date': pointing.date,
            'ra': pointing.coordinate.x,
            'dec': pointing.coordinate.y,
            'target_name': as_str(pointing.target),
            'telescope': pointing.telescope_id,
            'instrument': pointing.instrument_id,
            'filter': None,
            'exposure_time': as_float(extra.get('exposure_time')),
            'observation_type': None,
            'reduction_level': None,
            'processed': False,
            'proposal_id': None,
            'public_date': None,
        }
