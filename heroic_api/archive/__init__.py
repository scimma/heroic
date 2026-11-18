"""Searches of the public archives of HEROIC observatories, and of HEROIC's Rubin pointings, for frames of a target,
by position or by name.

Each archive is searched once per observing mode (imaging or spectroscopy), for every HEROIC instrument with data
in it, or for the requested ones. Each archive decides how many queries a search needs. The searches for a
request run in parallel, and the frames each one finds are normalised to fields common to all the archives. Each
archive names the instrument that took a frame by its own codes, which name the HEROIC instrument in the results.

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

When no telescopes or instruments are selected, the frames that archive searches find from instruments HEROIC doesn't
list are returned too, named by the archive's own telescope and instrument codes rather than HEROIC ids. NOIRLab
searches have to name their instruments, so they only find frames from the instruments HEROIC lists.

archive.py has the parts that every archive shares, and each archive should have its own implementation file.
This module plans the searches for a request, from the archive of each instrument's observatory and the archive ids
and supported modes of the instrument and its telescope.
"""
from heroic_api.archive.archive import ArchiveModes, ArchiveSearch, MatchTypes, ReductionLevels, search_archives
from heroic_api.archive.gemini import GeminiArchive
from heroic_api.archive.lco import LcoArchive
from heroic_api.archive.noirlab import NoirlabArchive
from heroic_api.archive.rubin import RubinArchive
from heroic_api.models import Instrument
from heroic_api.tasks import RUBIN_TELESCOPE_ID

__all__ = [
    'ARCHIVE_CHOICES', 'ArchiveModes', 'ArchiveSearch', 'MatchTypes', 'ReductionLevels',
    'archive_searches', 'instrument_archive_modes', 'search_archives',
]

LCO = LcoArchive()
NOIRLAB = NoirlabArchive()
GEMINI = GeminiArchive()
RUBIN = RubinArchive()

# Each archive's id and name
ARCHIVE_CHOICES = [(archive.id, archive.name) for archive in (LCO, NOIRLAB, GEMINI, RUBIN)]

# The archive holding the data of each HEROIC observatory's instruments, keyed by HEROIC observatory id
OBSERVATORY_ARCHIVES = {
    'lco': LCO,
    'ctio': NOIRLAB,
    'noirlab': NOIRLAB,
    'gemini': GEMINI,
}

# Telescopes whose data is searched somewhere other than their observatory's archive, keyed by HEROIC telescope id
TELESCOPE_ARCHIVES = {
    RUBIN_TELESCOPE_ID: RUBIN,
}

# The instrument capability that frames in each observing mode need
MODE_CAPABILITIES = {
    ArchiveModes.IMAGING: Instrument.SupportedModes.IMAGER,
    ArchiveModes.SPECTROSCOPY: Instrument.SupportedModes.SPECTROGRAPH,
}


def instrument_archive_modes(instrument) -> list:
    """Get the archive holding an instrument's frames, paired with each observing mode it has frames in there

    Parameters:
        instrument: A HEROIC Instrument
    Returns:
        list of (Archive, mode) pairs, or an empty list if no supported archive has the instrument's frames
    """
    archive = (TELESCOPE_ARCHIVES.get(instrument.telescope_id)
               or OBSERVATORY_ARCHIVES.get(instrument.telescope.site.observatory_id))
    if archive is None:
        return []
    return [(archive, mode) for mode, capability in MODE_CAPABILITIES.items()
            if capability in instrument.supported_modes and archive.instrument_keys(instrument, mode)]


def archive_searches(mode: str, selected=None) -> list:
    """Plan the archive searches for a request, one per archive and observing mode

    Parameters:
        mode: ArchiveModes value to limit the searches to
        selected: set of HEROIC Instruments to search for, or None to search for every instrument
    Returns:
        list of ArchiveSearch for the archives and modes that the instruments searched for have frames in
    """
    instruments_by_search = {}
    for instrument in Instrument.objects.select_related('telescope__site').order_by('id'):
        for archive, instrument_mode in instrument_archive_modes(instrument):
            if mode in (ArchiveModes.ALL, instrument_mode):
                instruments_by_search.setdefault((archive, instrument_mode), []).append(instrument)
    searches = []
    for (archive, search_mode), instruments in instruments_by_search.items():
        chosen = [instrument for instrument in instruments if selected is None or instrument in selected]
        if chosen:
            # If all or no instruments are selected, then we do a search without instrument id if possible
            # and return ALL results, even instruments that aren't within HEROIC
            complete = len(chosen) == len(instruments)
            searches.append(ArchiveSearch(archive, search_mode, tuple(chosen), complete))
    return searches
