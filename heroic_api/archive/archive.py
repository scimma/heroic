""" Base class for searching multiple Observatory archives together and returning the results

This has the request options, the base class that each archive's searches extend, running a set of searches
in parallel, and helpers for normalising the archives' results.
"""
import logging
import math
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import numpy as np
import requests
from astropy.coordinates import SkyCoord
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ArchiveModes(models.TextChoices):
    ALL = 'all', _('All')
    IMAGING = 'imaging', _('Imaging')
    SPECTROSCOPY = 'spectroscopy', _('Spectroscopy')


class ReductionLevels(models.TextChoices):
    ALL = 'all', _('All')
    RAW = 'raw', _('Raw')
    PROCESSED = 'processed', _('Processed')


class MatchTypes(models.TextChoices):
    EXACT = 'exact', _('The frame covers the position')
    APPROXIMATE = 'approximate', _('The frame was taken near the position')
    NAME = 'name', _("The frame's target name matches")


# For archives that can only match spectroscopy files approximately by the frames central position.
SPECTRUM_BOX_HALF_WIDTH = 40 / 3600  # degrees


@dataclass(frozen=True)
class ArchiveQuery:
    """The parts of an archive request that every search uses"""
    start: datetime
    end: datetime
    reduction_level: str
    row_limit: int
    # A target name to search for, or empty to search around ra and dec instead
    target_name: str = ''
    ra: float = None
    dec: float = None

    @property
    def coordinate(self) -> SkyCoord:
        # Each caller gets its own SkyCoord, since searches run in separate threads
        return SkyCoord(self.ra, self.dec, unit='deg')


@dataclass
class SearchResult:
    """Normalised frames from one archive search, newest first, and whether the archive held more"""
    frames: list
    truncated: bool


@dataclass(frozen=True)
class ArchiveSearch:
    """A search of one archive for frames in one observing mode, from one instrument or from several.

    Searches are frozen so they can be compared and used as dict keys.
    """
    # The archive's id in search results, and its name
    archive: ClassVar[str] = ''
    archive_name: ClassVar[str] = ''
    # Should run the search in the local thread or not. Local thread is needed for HEROIC DB access.
    runs_locally: ClassVar[bool] = False
    mode: str

    @property
    def match(self) -> str:
        """Whether a matching frame covers the position (exact) or was taken near it (approximate)"""
        if self.mode == ArchiveModes.IMAGING:
            return MatchTypes.EXACT
        return MatchTypes.APPROXIMATE

    def combine_key(self) -> tuple:
        """Searches of the same archive with the same key can be combined into one search"""
        return (self.mode,)

    @classmethod
    def combine(cls, searches: list) -> 'ArchiveSearch':
        """Group up a list of searches into a single search if possible"""
        raise NotImplementedError

    def covers(self, frame: dict) -> bool:
        """Whether this search would find a frame, which names its telescope and instrument in the archive's codes.

        This tells which instrument's search a frame from a combined search belongs to.
        """
        raise NotImplementedError

    def run(self, query: ArchiveQuery) -> SearchResult:
        raise NotImplementedError


def combine_searches(plan: dict) -> dict:
    """Combine a plan's searches into one search per archive and type of search, to make fewer archive queries

    Searches are combined if possible when no specific telescopes/instruments are selected.

    A combined search finds frames from several instruments, so each instrument keeps its own search.
    _clean_search_results uses them to give each frame the HEROIC ids of the instrument whose own search covers it.

    Parameters:
        plan: dict of each ArchiveSearch to the instruments it finds frames for, each mapped to its own search.
            Before combining, an instrument's own search is the key itself.
    Returns:
        dict of the same form, with each combined ArchiveSearch mapped to the instruments of the searches it
        replaced
    """
    groups = {}
    for search in plan:
        groups.setdefault((type(search), search.combine_key()), []).append(search)
    combined = {}
    for (search_class, _key), searches in groups.items():
        combined[search_class.combine(searches)] = {
            instrument: member for search in searches for instrument, member in plan[search].items()
        }
    return combined


def search_archives(data: dict) -> dict:
    """Search the archives for public frames of a target, by name if one is given or else around ra and dec

    The searches run in parallel. Any still running after settings.ARCHIVE_QUERY_TIMEOUT seconds are
    reported as timed out, and a search that fails reports its error without affecting the others.
    Parameters:
        data: The validated data from the ArchiveQuerySerializer
    Returns:
        dict with 'searches', the outcome of each archive search including the frames it found, newest first
    """
    query = ArchiveQuery(
        start=data['start'], end=data['end'], reduction_level=data['reduction_level'], row_limit=data['row_limit'],
        target_name=data.get('target_name') or '', ra=data.get('ra'), dec=data.get('dec')
    )
    plan = data['searches']
    timeout = settings.ARCHIVE_QUERY_TIMEOUT
    executor = ThreadPoolExecutor(max_workers=max(1, min(len(plan), settings.ARCHIVE_QUERY_MAX_WORKERS)))
    try:
        futures = {search: executor.submit(search.run, query) for search in plan if not search.runs_locally}
        for search in plan:
            if search.runs_locally:
                futures[search] = _run_here(search, query)
        done, _not_done = wait(futures.values(), timeout=timeout)
    finally:
        # Don't wait for searches that are still running. Their own request timeouts will end them.
        executor.shutdown(wait=False, cancel_futures=True)

    searches = []
    for search, members in plan.items():
        future = futures[search]
        outcome = {
            'archive': search.archive,
            'mode': search.mode,
            'match': MatchTypes.NAME if query.target_name else search.match,
            'telescopes': sorted({instrument.telescope_id for instrument in members}),
            'instruments': [instrument.id for instrument in members],
            'count': 0,
            'truncated': False,
            'error': None,
            'frames': [],
        }
        if future not in done:
            outcome['error'] = f'The search did not finish within {timeout:g} seconds'
        elif future.exception() is not None:
            logger.warning(f'Archive search {search} failed', exc_info=future.exception())
            outcome['error'] = _error_message(future.exception())
        else:
            result = future.result()
            outcome['frames'] = _clean_search_results(result.frames, members)
            outcome['count'] = len(outcome['frames'])
            outcome['truncated'] = result.truncated
        searches.append(outcome)

    return {'searches': searches}


def _run_here(search: ArchiveSearch, query: ArchiveQuery) -> Future:
    """Run a search in this thread, giving its outcome as a finished future like the other searches'"""
    future = Future()
    try:
        future.set_result(search.run(query))
    except Exception as exception:
        future.set_exception(exception)
    return future


def _clean_search_results(frames: list, members: dict) -> list:
    """Give frames the HEROIC ids of the instruments that took them, and leave out frames from other instruments

    HEROIC should list each archive instrument only once, so at most one instrument's own search covers a frame.
    Parameters:
        frames: Frames found by a search, which name their telescope and instrument in the archive's codes
        members: dict of the instruments the search finds frames for, each mapped to its own search
    Returns:
        The frames that an instrument's own search covers, with that instrument's HEROIC telescope and instrument ids
    """
    cleaned = []
    for frame in frames:
        for instrument, search in members.items():
            if search.covers(frame):
                cleaned.append({**frame, 'telescope': instrument.telescope_id, 'instrument': instrument.id})
                break
    return cleaned


def _error_message(exception: Exception) -> str:
    if isinstance(exception, requests.exceptions.Timeout):
        return 'The archive did not respond in time'
    if isinstance(exception, requests.exceptions.ConnectionError):
        return 'Could not connect to the archive'
    if isinstance(exception, requests.exceptions.HTTPError) and exception.response is not None:
        return f'The archive returned HTTP status {exception.response.status_code}'
    return f'The search failed: {type(exception).__name__}: {exception}'[:500]

# Helper functions for archive implementations to use

def half_diagonal(width_arcmin: float, height_arcmin: float) -> float:
    """Radius in degrees of the circle that holds a width x height field of view at any rotation"""
    return math.hypot(width_arcmin, height_arcmin) / 2 / 60


def within_field_of_view(frames: list, coordinate: SkyCoord, field_radii: dict, margin: float = 0.0) -> list:
    """Keep the frames whose recorded position is close enough to coordinate for their instrument's field to cover it

    Parameters:
        frames: Normalised frames
        coordinate: The position searched around
        field_radii: dict of each instrument's field radius in degrees, keyed by the archive's instrument code
        margin: Degrees to add to every field radius
    Returns:
        The frames within their instrument's field radius plus the margin of coordinate
    """
    frames = [frame for frame in frames
              if frame['ra'] is not None and frame['dec'] is not None and frame['instrument'] in field_radii]
    if not frames:
        return []
    centers = SkyCoord([frame['ra'] for frame in frames], [frame['dec'] for frame in frames], unit='deg')
    separations = centers.separation(coordinate).deg
    return [frame for frame, separation in zip(frames, separations)
            if separation <= field_radii[frame['instrument']] + margin]


def search_result(frames: list, row_limit: int, truncated: bool = False) -> SearchResult:
    """Sort frames with the newest first and keep row_limit of them, noting whether any were left out"""
    frames.sort(key=lambda frame: frame['observation_date'], reverse=True)
    return SearchResult(frames=frames[:row_limit], truncated=truncated or len(frames) > row_limit)


def archive_codes(instrument) -> tuple:
    """An instrument's codes in its archive, from its archive id, which separates several with commas"""
    return tuple(code.strip() for code in instrument.archive_id.split(',') if code.strip())


def union(groups) -> tuple:
    """The distinct values in groups of values, sorted"""
    return tuple(sorted({value for values in groups for value in values}))


def as_str(value):
    """A table value as a string, or None if it's missing"""
    return None if value is None or value is np.ma.masked else str(value)


def as_float(value):
    """A table value as a float, or None if it's missing"""
    return None if value is None or value is np.ma.masked else float(value)
