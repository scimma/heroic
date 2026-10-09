"""Searches of the public archives of HEROIC observatories, and of HEROIC's Rubin pointings, for frames of a target,
by position or by name.

Each HEROIC instrument whose data is in one of these archives maps to one or more archive searches,
one per observing mode (imaging or spectroscopy). When particular telescopes or instruments are
requested, each of their searches is a separate archive query. When every instrument is requested,
the searches of each archive are combined, so each archive is queried once per kind of search rather
than once per instrument. The searches for a request run in parallel, and the frames each one finds
are normalised to fields common to all the archives.

A search by target name matches the name the observer recorded with each frame, ignoring case, so it
finds no frames recorded under other names for the same target. Searches by position match differently
at each archive, so every search is marked as an exact or approximate match:
    - LCO returns the frames whose footprint contains the position, so its imaging matches are exact. A spectrum's
      footprint is its slit with some padding, so its spectroscopy matches are approximate.
    - NOIRLab and Gemini match each frame's recorded position against a box around the position, so their
      matches are approximate. Imaging boxes hold the instrument's field of view at any rotation and are then cut
      on distance. NOIRLab's also add a margin, since a raw file's center comes from its header pointing.
    - NOIRLab and Gemini don't record where a spectrograph's slit was, so their spectra match a box of +/-40"
      around each frame's recorded position.
    - Rubin's performed pointings, which HEROIC stores from the Rubin schedule, match when their field of view
      contains the position, so these matches are exact. HEROIC has no files for them.

Only public data is returned.

archive.py has the parts that every archive shares, and each archive should have its own implementation file.
This module maps HEROIC instruments to the searches that find their frames, from the archive of each
instrument's observatory and the archive ids and supported modes of the instrument and its telescope.
"""
from heroic_api.archive.archive import (ArchiveModes, ArchiveSearch, MatchTypes, ReductionLevels, combine_searches,
                                        search_archives)
from heroic_api.archive.gemini import GeminiSearch, gemini_searches
from heroic_api.archive.lco import LcoSearch, lco_searches
from heroic_api.archive.noirlab import NoirlabSearch, noirlab_searches
from heroic_api.archive.rubin import RubinSearch, rubin_searches
from heroic_api.tasks import RUBIN_TELESCOPE_ID

__all__ = [
    'ARCHIVE_CHOICES', 'ArchiveModes', 'ArchiveSearch', 'MatchTypes', 'ReductionLevels',
    'archive_searches_for_instrument', 'archive_searches_for_instruments', 'search_archives',
]

# Each archive's id and name, from its search class
ARCHIVE_CHOICES = [(search_class.archive, search_class.archive_name)
                   for search_class in (LcoSearch, NoirlabSearch, GeminiSearch, RubinSearch)]

# The function that gets an instrument's searches of the archive holding its observatory's data,
# keyed by HEROIC observatory id
OBSERVATORY_SEARCHES = {
    'lco': lco_searches,
    'ctio': noirlab_searches,
    'noirlab': noirlab_searches,
    'gemini': gemini_searches,
}

# Telescopes whose data is searched somewhere other than their observatory's archive, keyed by HEROIC telescope id
TELESCOPE_SEARCHES = {
    RUBIN_TELESCOPE_ID: rubin_searches,
}


def archive_searches_for_instrument(instrument) -> list:
    """Get the archive searches that find an instrument's frames

    Parameters:
        instrument: A HEROIC Instrument
    Returns:
        list of ArchiveSearch, one per observing mode, or an empty list if no supported archive has its data
    """
    searches = (TELESCOPE_SEARCHES.get(instrument.telescope_id)
                or OBSERVATORY_SEARCHES.get(instrument.telescope.site.observatory_id))
    if searches is None:
        return []
    return searches(instrument)


def archive_searches_for_instruments(instruments, mode: str = ArchiveModes.ALL, combine: bool = False) -> dict:
    """Get the archive searches needed to find the frames of a set of instruments

    Parameters:
        instruments: HEROIC Instruments to search for
        mode: ArchiveModes value to limit the searches to
        combine: Combine each archive's searches into one per kind of search, rather than one per instrument.
            This makes far fewer archive queries when searching for every instrument.
    Returns:
        dict of each ArchiveSearch to a dict of the instruments it finds frames for, each mapped to the search
        that finds that instrument's frames on its own. Instruments needing the same search share one entry.
    """
    plan = {}
    for instrument in sorted(set(instruments), key=lambda instrument: instrument.id):
        for search in archive_searches_for_instrument(instrument):
            if mode in (ArchiveModes.ALL, search.mode):
                plan.setdefault(search, {})[instrument] = search
    return combine_searches(plan) if combine else plan
