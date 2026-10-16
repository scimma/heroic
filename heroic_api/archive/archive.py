""" Base class for searching multiple Observatory archives together and returning the results

This has the request options, the base class that each archive extends, running a set of archive searches
in parallel and naming each frame by the HEROIC instrument that took it, and helpers for normalising the
archives' results.
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
    """Normalised frames from one archive search, and whether the archive held more"""
    frames: list
    truncated: bool


class Archive:
    """An archive that HEROIC searches for frames. Each archive's module has a subclass.

    An archive names the instrument that took each frame by its own codes. instrument_keys and frame_key turn a
    HEROIC instrument and a frame into the same key, so search_archives can name each frame by its HEROIC instrument.
    """
    # The archive's id in search results, and its name
    id: ClassVar[str] = ''
    name: ClassVar[str] = ''
    # Should run the search in the local thread or not. Local thread is needed for HEROIC DB access.
    runs_locally: ClassVar[bool] = False

    def match(self, mode: str) -> str:
        """Whether a frame found in a mode covers the position (exact) or was taken near it (approximate)"""
        if mode == ArchiveModes.IMAGING:
            return MatchTypes.EXACT
        return MatchTypes.APPROXIMATE

    def instrument_keys(self, instrument, mode: str) -> list:
        """The keys that name a HEROIC instrument's frames in a mode it supports, as frame_key gives them, or an
        empty list if the archive has none of its frames in that mode
        """
        raise NotImplementedError

    def frame_key(self, frame: dict):
        """The key that names the instrument that took a frame, from the archive's codes in the frame"""
        raise NotImplementedError

    def fetch(self, query: ArchiveQuery, search: 'ArchiveSearch') -> SearchResult:
        """Query the archive for the frames of a search's instruments.

        Each query keeps the newest row_limit frames it finds, and the result is truncated if any query had more.
        The frames name their telescope and instrument by the archive's codes. They can include frames from other
        instruments, and needn't be sorted, since search_archives sorts them out.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class ArchiveSearch:
    """A search of one archive for frames in one observing mode, from some of its HEROIC instruments"""
    archive: Archive
    mode: str
    instruments: tuple
    # Whether the instruments are all of the archive's HEROIC instruments in this mode, so the archive needn't narrow
    # its queries down to them
    complete: bool


def search_archives(data: dict) -> dict:
    """Search the archives for public frames of a target, by name if one is given or else around ra and dec

    The searches run in parallel. Any still running after settings.ARCHIVE_QUERY_TIMEOUT seconds are
    reported as timed out, and a search that fails reports its error without affecting the others.
    Each frame is named by the HEROIC telescope and instrument that took it. Frames from instruments HEROIC doesn't
    list keep the archive's codes, and are only returned when no telescopes or instruments are selected.
    Parameters:
        data: The validated data from the ArchiveQuerySerializer
    Returns:
        dict with 'searches', the outcome of each archive search including the frames it found, newest first
    """
    query = ArchiveQuery(
        start=data['start'], end=data['end'], reduction_level=data['reduction_level'], row_limit=data['row_limit'],
        target_name=data.get('target_name') or '', ra=data.get('ra'), dec=data.get('dec')
    )
    include_unlisted = not (data.get('telescopes') or data.get('instruments'))
    searches = data['searches']
    timeout = settings.ARCHIVE_QUERY_TIMEOUT
    executor = ThreadPoolExecutor(max_workers=max(1, min(len(searches), settings.ARCHIVE_QUERY_MAX_WORKERS)))
    try:
        futures = {search: executor.submit(search.archive.fetch, query, search)
                   for search in searches if not search.archive.runs_locally}
        for search in searches:
            if search.archive.runs_locally:
                futures[search] = _run_here(search, query)
        done, _not_done = wait(futures.values(), timeout=timeout)
    finally:
        # Don't wait for searches that are still running. Their own request timeouts will end them.
        executor.shutdown(wait=False, cancel_futures=True)

    outcomes = []
    for search in searches:
        future = futures[search]
        outcome = {
            'archive': search.archive.id,
            'mode': search.mode,
            'match': MatchTypes.NAME if query.target_name else search.archive.match(search.mode),
            'telescopes': sorted({instrument.telescope_id for instrument in search.instruments}),
            'instruments': [instrument.id for instrument in search.instruments],
            'count': 0,
            'truncated': False,
            'error': None,
            'frames': [],
        }
        if future not in done:
            outcome['error'] = f'The search did not finish within {timeout:g} seconds'
        elif future.exception() is not None:
            logger.warning(f'The {search.archive.id} {search.mode} search failed', exc_info=future.exception())
            outcome['error'] = _error_message(future.exception())
        else:
            result = future.result()
            # HEROIC lists each archive instrument once, so each key names one instrument
            instruments = {key: instrument for instrument in search.instruments
                           for key in search.archive.instrument_keys(instrument, search.mode)}
            frames = []
            for frame in result.frames:
                instrument = instruments.get(search.archive.frame_key(frame))
                if instrument is not None:
                    frames.append({**frame, 'telescope': instrument.telescope_id, 'instrument': instrument.id})
                elif include_unlisted:
                    frames.append(frame)
            # A search with several queries returns all of their frames together
            frames.sort(key=lambda frame: frame['observation_date'], reverse=True)
            outcome['frames'] = frames
            outcome['count'] = len(frames)
            outcome['truncated'] = result.truncated
        outcomes.append(outcome)

    return {'searches': outcomes}


def _run_here(search: ArchiveSearch, query: ArchiveQuery) -> Future:
    """Run a search in this thread, giving its outcome as a finished future like the other searches'"""
    future = Future()
    try:
        future.set_result(search.archive.fetch(query, search))
    except Exception as exception:
        future.set_exception(exception)
    return future


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
