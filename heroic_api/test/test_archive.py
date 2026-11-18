import threading
from datetime import datetime, timezone
from unittest.mock import patch

import astropy.units as u
import requests
from astropy.table import MaskedColumn, Table
from astroquery.lco.core import RESULT_COLUMNS as LCO_COLUMNS
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from mixer.backend.django import mixer
from rest_framework.test import APITestCase

from heroic_api import models
from heroic_api.archive.noirlab import NOIRLAB_FIELDS, NOIRLAB_GOODMAN_FIELDS
from heroic_api.serializers import ArchiveFrameSerializer, ArchiveSearchResultSerializer
from heroic_api.tasks import RUBIN_INSTRUMENT_ID, RUBIN_TELESCOPE_ID


# M101
RA = 210.802429
DEC = 54.348750

LCO_FRAME = {
    'id': 1001,
    'basename': 'tfn1m014-fa20-20240305-0001-e91',
    'filename': 'tfn1m014-fa20-20240305-0001-e91.fits.fz',
    'observation_date': '2024-03-05T02:16:32.326000Z',
    'observation_day': '2024-03-04',
    'proposal_id': 'LCO2024A-001',
    'target_name': 'M101',
    'ra': RA,
    'dec': DEC,
    'site_id': 'tfn',
    'telescope_id': '1m0a',
    'instrument_id': 'fa20',
    'configuration_type': 'EXPOSE',
    'primary_optical_element': 'rp',
    'exposure_time': 30.0,
    'reduction_level': 91,
    'observation_id': 10,
    'request_id': 20,
    'public_date': '2025-03-05T02:16:32.326000Z',
    'url': 'https://archive.example/tfn1m014-fa20-20240305-0001-e91.fits.fz',
}

NOIRLAB_FILE = {
    'md5sum': '89d1559d6016864f6d9b37d5bd948503',
    'url': 'https://astroarchive.noirlab.edu/api/retrieve/89d1559d6016864f6d9b37d5bd948503/',
    'archive_filename': '/net/archive/pipe/20240729/ct4m/2024A-697040/c4d_240730_023515_ooi_z_v1.fits.fz',
    'telescope': 'ct4m',
    'instrument': 'decam',
    'obs_type': 'object',
    'proc_type': 'instcal',
    'prod_type': 'image',
    'dateobs_center': '2024-07-30T02:35:40.798000Z',
    'ra_center': RA,
    'dec_center': DEC,
    'release_date': '2024-07-29',
    'ifilter': 'z DECam SDSS c0004 9260.0 1520.0',
    'exposure': 50.0,
    'proposal': '2024A-697040',
    'OBJECT': 'M101',
}

GEMINI_FRAME = {
    'data_label': 'GN-2023A-DD-105-82-016',
    'filename': 'N20230605S0078.fits.bz2',
    'ut_datetime': '2023-06-05 10:38:41.700000',
    'ra': '210.738557947646',
    'dec': '54.318238373026',
    'object': 'SN 2023ixf',
    'telescope': 'Gemini-North',
    'instrument': 'GMOS-N',
    'filter_name': 'i',
    'exposure_time': '60.0',
    'observation_type': 'OBJECT',
    'reduction': 'RAW',
    'program_id': 'GN-2023A-DD-105',
    'release': '2023-06-05',
    'mode': 'imaging',
}


def lco_table(*frames):
    """A table shaped like the results of the astroquery LCO module's queries"""
    if not frames:
        return Table(names=LCO_COLUMNS, dtype=[object] * len(LCO_COLUMNS))
    rows = [{**LCO_FRAME, **frame} for frame in frames]
    table = Table([[row[name] for row in rows] for name in LCO_COLUMNS], names=LCO_COLUMNS)
    for name in ('ra', 'dec'):
        table[name] = MaskedColumn([row[name] for row in rows], unit=u.deg)
    return table


def noirlab_table(*files, fields=NOIRLAB_FIELDS):
    """A table shaped like the results of the astroquery NOIRLab module's query_metadata"""
    if not files:
        # NOIRLab's empty results have float columns
        return Table(names=fields, dtype=[float] * len(fields))
    rows = [{**NOIRLAB_FILE, **file} for file in files]
    return Table(names=fields, rows=[[row.get(name) for name in fields] for row in rows])


def gemini_table(*frames):
    """A table shaped like the results of the astroquery Gemini module's queries, where every column is text"""
    rows = [{**GEMINI_FRAME, **frame} for frame in frames]
    table = Table(masked=True)
    for name in GEMINI_FRAME:
        values = [row[name] for row in rows]
        table[name] = MaskedColumn([str(value) for value in values], mask=[value is None for value in values],
                                   dtype=str)
    return table


class BaseArchiveTestCase(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        imager = [models.Instrument.SupportedModes.IMAGER]
        spectrograph = [models.Instrument.SupportedModes.SPECTROGRAPH]
        # LCO telescopes, with an autoguider that has no supported modes
        lco = mixer.blend(models.Observatory, id='lco')
        tfn = mixer.blend(models.Site, id='lco.tfn', observatory=lco, elevation=2000)
        ogg = mixer.blend(models.Site, id='lco.ogg', observatory=lco, elevation=3000)
        lsc = mixer.blend(models.Site, id='lco.lsc', observatory=lco, elevation=2000)
        self.tfn_1m = mixer.blend(models.Telescope, id='lco.tfn.domb-1m0a', site=tfn, archive_id='1m0a')
        self.ogg_2m = mixer.blend(models.Telescope, id='lco.ogg.clma-2m0a', site=ogg, archive_id='2m0a')
        # The enclosure of an NRES unit, which the archive files its frames under
        self.lsc_igla = mixer.blend(models.Telescope, id='lco.lsc.igla-1m0a', site=lsc, archive_id='igla')
        self.sinistro = mixer.blend(models.Instrument, id='lco.tfn.domb-1m0a.fa20', telescope=self.tfn_1m,
                                    archive_id='fa20', supported_modes=imager)
        self.autoguider = mixer.blend(models.Instrument, id='lco.tfn.domb-1m0a.ef01', telescope=self.tfn_1m)
        # MuSCAT, with its four cameras
        self.muscat = mixer.blend(models.Instrument, id='lco.ogg.clma-2m0a.mc03', telescope=self.ogg_2m,
                                  archive_id='ep02,ep03,ep04,ep05', supported_modes=imager)
        self.floyds = mixer.blend(models.Instrument, id='lco.ogg.clma-2m0a.floyds01', telescope=self.ogg_2m,
                                  archive_id='en06', supported_modes=spectrograph)
        self.nres = mixer.blend(models.Instrument, id='lco.lsc.igla-1m0a.nres01', telescope=self.lsc_igla,
                                archive_id='fa09', supported_modes=spectrograph)
        # CTIO telescopes, whose data is at NOIRLab
        ctio = mixer.blend(models.Observatory, id='ctio')
        ct = mixer.blend(models.Site, id='ctio.ct', observatory=ctio, elevation=2200)
        cp = mixer.blend(models.Site, id='ctio.cp', observatory=ctio, elevation=2700)
        self.blanco = mixer.blend(models.Telescope, id='ctio.ct.blanco', site=ct, archive_id='ct4m')
        self.soar = mixer.blend(models.Telescope, id='ctio.cp.soar', site=cp, archive_id='soar')
        self.decam = mixer.blend(models.Instrument, id='ctio.ct.blanco.decam', telescope=self.blanco,
                                 archive_id='decam', supported_modes=imager)
        self.newfirm = mixer.blend(models.Instrument, id='ctio.ct.blanco.newfirm', telescope=self.blanco,
                                   archive_id='newfirm', supported_modes=imager)
        self.goodman_red = mixer.blend(models.Instrument, id='ctio.cp.soar.goodr', telescope=self.soar,
                                       archive_id='ghts_red,goodman', supported_modes=spectrograph)
        # Gemini North, with an adaptive optics system that has no data of its own
        gemini = mixer.blend(models.Observatory, id='gemini')
        mk = mixer.blend(models.Site, id='gemini.mk', observatory=gemini, elevation=4200)
        self.gemini_north = mixer.blend(models.Telescope, id='gemini.mk.gn', site=mk, archive_id='Gemini-North')
        self.gmos_n = mixer.blend(models.Instrument, id='gemini.mk.gn.gmos_n', telescope=self.gemini_north,
                                  archive_id='GMOS-N', supported_modes=imager + spectrograph)
        self.altair = mixer.blend(models.Instrument, id='gemini.mk.gn.altair', telescope=self.gemini_north)
        # Rubin, whose pointings HEROIC stores
        noirlab = mixer.blend(models.Observatory, id='noirlab')
        noirlab_cp = mixer.blend(models.Site, id='noirlab.cp', observatory=noirlab, elevation=2700)
        self.rubin = mixer.blend(models.Telescope, id=RUBIN_TELESCOPE_ID, site=noirlab_cp)
        self.lsstcam = mixer.blend(models.Instrument, id=RUBIN_INSTRUMENT_ID, telescope=self.rubin,
                                   supported_modes=imager)
        # A telescope with no data in a supported archive
        ligo = mixer.blend(models.Observatory, id='ligo')
        hanford = mixer.blend(models.Site, id='ligo.hanford', observatory=ligo, elevation=100)
        self.h1 = mixer.blend(models.Telescope, id='ligo.hanford.h1', site=hanford)
        mixer.blend(models.Instrument, id='ligo.hanford.h1.interferometer', telescope=self.h1)

        # Stand-ins for the astroquery clients, so the tests never query the real archives
        self.lco = self._patch('heroic_api.archive.lco.LcoArchiveClass')
        self.noirlab = self._patch('heroic_api.archive.noirlab.NOIRLabClass')
        self.gemini = self._patch('heroic_api.archive.gemini.GeminiObservationsClass')
        self.lco.return_value.query_region.return_value = lco_table()
        self.lco.return_value.query_criteria.return_value = lco_table()
        self.noirlab.return_value.query_metadata.return_value = noirlab_table()
        self.gemini.return_value.query_raw.return_value = gemini_table()

        self.query = {
            'ra': RA,
            'dec': DEC,
            'start': datetime(2023, 1, 1).isoformat(),
            'end': datetime(2024, 12, 31, 23, 59, 59).isoformat(),
        }

    def _patch(self, target):
        patcher = patch(target)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _search(self, response, archive):
        """The one search of an archive in a response"""
        searches = [search for search in response.json()['searches'] if search['archive'] == archive]
        self.assertEqual(len(searches), 1)
        return searches[0]


class TestArchiveQueryValidation(BaseArchiveTestCase):
    def test_query_without_authentication_fails(self):
        self.client.logout()
        response = self.client.get(reverse('api:archive-query'), data=self.query)
        self.assertContains(response, 'Authentication credentials were not provided', status_code=403)

    def test_dates_are_required(self):
        response = self.client.get(reverse('api:archive-query'), data={'ra': RA, 'dec': DEC})
        self.assertEqual(response.status_code, 400)
        for field in ('start', 'end'):
            self.assertIn(field, response.json())

    def test_position_must_be_a_number(self):
        for field in ('ra', 'dec'):
            response = self.client.get(reverse('api:archive-query'), data={**self.query, field: 'nan'})
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json())

    def test_target_name_or_position_is_required(self):
        query = {'start': self.query['start'], 'end': self.query['end']}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertContains(response, 'either a target_name, or ra and dec', status_code=400)

    def test_target_name_searches_each_archive_by_name_instead_of_position(self):
        self.lco.return_value.query_criteria.return_value = lco_table({})
        query = {'target_name': 'M101', 'start': self.query['start'], 'end': self.query['end'],
                 'instruments': [self.sinistro.id, self.decam.id, self.gmos_n.id], 'mode': 'imaging'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({search['match'] for search in response.json()['searches']}, {'name'})
        self.assertEqual(self._search(response, 'lco')['count'], 1)

        self.lco.return_value.query_region.assert_not_called()
        self.assertEqual(self.lco.return_value.query_criteria.call_args.kwargs['target_name_iexact'], 'M101')
        noirlab_terms = self.noirlab.return_value.query_metadata.call_args.args[0]['search']
        self.assertIn(['OBJECT', 'M101', 'iexact'], noirlab_terms)
        self.assertNotIn('ra_center', [term[0] for term in noirlab_terms])
        # NOIRLab rejects searches on header fields without a proc_type term
        self.assertIn('proc_type', [term[0] for term in noirlab_terms])
        gemini_options = self.gemini.return_value.query_raw.call_args.kwargs
        self.assertEqual(gemini_options['object'], 'M101')
        self.assertNotIn('coordinates', gemini_options)

    def test_end_must_be_after_start(self):
        query = {**self.query, 'start': self.query['end'], 'end': self.query['start']}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn('end', response.json())

    def test_instrument_without_archive_data_fails(self):
        query = {**self.query, 'instruments': [self.gmos_n.id, self.altair.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn(self.altair.id, response.json()['instruments'][0])
        self.assertNotIn(self.gmos_n.id, response.json()['instruments'][0])

    def test_telescope_without_archive_data_fails(self):
        query = {**self.query, 'telescopes': [self.h1.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertContains(response, 'have data in a supported archive', status_code=400)

    def test_instruments_must_be_on_the_selected_telescopes(self):
        query = {**self.query, 'telescopes': [self.tfn_1m.id], 'instruments': [self.floyds.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn(self.floyds.id, response.json()['instruments'][0])


class TestArchiveSearchPlanning(BaseArchiveTestCase):
    def _searched(self, response):
        return {(search['archive'], search['mode'], tuple(search['instruments']))
                for search in response.json()['searches']}

    def _query_count(self):
        return (self.lco.return_value.query_region.call_count
                + self.noirlab.return_value.query_metadata.call_count
                + self.gemini.return_value.query_raw.call_count)

    def test_every_instrument_is_searched_with_one_query_per_archive_and_kind_by_default(self):
        response = self.client.get(reverse('api:archive-query'), data=self.query)
        self.assertEqual(response.status_code, 200)
        # Instruments without supported modes, like the autoguider and adaptive optics system, have no archive
        # searches, and neither do observatories without an archive, like LIGO
        self.assertEqual(self._searched(response), {
            ('lco', 'imaging', (self.muscat.id, self.sinistro.id)),
            ('lco', 'spectroscopy', (self.nres.id, self.floyds.id)),
            ('noirlab', 'imaging', (self.decam.id, self.newfirm.id)),
            ('noirlab', 'spectroscopy', (self.goodman_red.id,)),
            ('gemini', 'imaging', (self.gmos_n.id,)),
            ('gemini', 'spectroscopy', (self.gmos_n.id,)),
            ('rubin', 'imaging', (self.lsstcam.id,)),
        })
        self.assertEqual(self._query_count(), 6)

    def test_selected_lco_instruments_are_queried_one_at_a_time(self):
        # An LCO imager that isn't selected, so the selected imagers can't share one query of every LCO frame
        tfn_0m4 = mixer.blend(models.Telescope, id='lco.tfn.aqwa-0m4a', site=self.tfn_1m.site, archive_id='0m4a')
        mixer.blend(models.Instrument, id='lco.tfn.aqwa-0m4a.sq32', telescope=tfn_0m4, archive_id='sq32',
                    supported_modes=[models.Instrument.SupportedModes.IMAGER])
        query = {**self.query, 'telescopes': [self.tfn_1m.id, self.ogg_2m.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(self._searched(response), {
            ('lco', 'imaging', (self.muscat.id, self.sinistro.id)),
            ('lco', 'spectroscopy', (self.floyds.id,)),
        })
        self.assertEqual(self._query_count(), 3)

    def test_selecting_every_lco_instrument_of_a_mode_queries_them_together(self):
        # Every LCO spectrograph, but only one of its imagers
        query = {**self.query, 'telescopes': [self.ogg_2m.id, self.lsc_igla.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(self._searched(response), {
            ('lco', 'imaging', (self.muscat.id,)),
            ('lco', 'spectroscopy', (self.nres.id, self.floyds.id)),
        })
        self.assertEqual(self._query_count(), 2)

    def test_frames_are_named_by_their_heroic_instrument_or_archive_codes(self):
        self.lco.return_value.query_region.return_value = lco_table(
            {'id': 1},
            # One of MuSCAT's cameras, and the camera it replaced on the same telescope
            {'id': 2, 'site_id': 'ogg', 'telescope_id': '2m0a', 'instrument_id': 'ep04'},
            {'id': 3, 'site_id': 'ogg', 'telescope_id': '2m0a', 'instrument_id': 'fs02'},
            # A camera HEROIC doesn't list, and a site without HEROIC instruments
            {'id': 4, 'instrument_id': 'fa11'},
            {'id': 5, 'site_id': 'sor', 'telescope_id': '4m0a', 'instrument_id': 'ghts_red_imager'},
        )
        response = self.client.get(reverse('api:archive-query'), data={**self.query, 'mode': 'imaging'})
        frames = self._search(response, 'lco')['frames']
        self.assertEqual({frame['id']: (frame['telescope'], frame['instrument']) for frame in frames}, {
            '1': (self.tfn_1m.id, self.sinistro.id),
            '2': (self.ogg_2m.id, self.muscat.id),
            '3': ('ogg.2m0a', 'fs02'),
            '4': ('tfn.1m0a', 'fa11'),
            '5': ('sor.4m0a', 'ghts_red_imager'),
        })

    def test_selected_telescopes_leave_out_frames_from_unlisted_instruments(self):
        self.lco.return_value.query_region.return_value = lco_table(
            {'id': 1, 'site_id': 'ogg', 'telescope_id': '2m0a', 'instrument_id': 'en06',
             'configuration_type': 'SPECTRUM'},
            # A FLOYDS that HEROIC doesn't list
            {'id': 2, 'site_id': 'coj', 'telescope_id': '2m0a', 'instrument_id': 'en12',
             'configuration_type': 'SPECTRUM'},
        )
        # Every LCO spectrograph, so they share one query of every LCO spectrum
        query = {**self.query, 'telescopes': [self.ogg_2m.id, self.lsc_igla.id], 'mode': 'spectroscopy'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        frames = self._search(response, 'lco')['frames']
        self.assertEqual({frame['id']: frame['instrument'] for frame in frames}, {'1': self.floyds.id})

    def test_lco_spectra_are_named_by_their_camera_and_telescope(self):
        nres = {'site_id': 'lsc', 'instrument_id': 'fa09', 'configuration_type': 'TARGET'}
        self.lco.return_value.query_region.return_value = lco_table(
            {'id': 1, 'telescope_id': 'igla', **nres},
            # The copy of an NRES raw frame that the archive files under a placeholder telescope
            {'id': 2, 'telescope_id': '1m0a', **nres},
            {'id': 3, 'site_id': 'ogg', 'telescope_id': '2m0a', 'instrument_id': 'en06',
             'configuration_type': 'SPECTRUM'},
        )
        response = self.client.get(reverse('api:archive-query'), data={**self.query, 'mode': 'spectroscopy'})
        frames = self._search(response, 'lco')['frames']
        self.assertEqual({frame['id']: frame['instrument'] for frame in frames},
                         {'1': self.nres.id, '3': self.floyds.id})

    def test_goodman_files_under_its_old_code_are_named_by_the_camera_that_took_them(self):
        goodman_blue = mixer.blend(models.Instrument, id='ctio.cp.soar.goodb', telescope=self.soar,
                                   archive_id='ghts_blue,goodman',
                                   supported_modes=[models.Instrument.SupportedModes.SPECTROGRAPH])
        goodman = {'telescope': 'soar', 'instrument': 'goodman', 'proc_type': 'raw', 'GRATING': 'SYZY_400'}
        self.noirlab.return_value.query_metadata.return_value = noirlab_table(
            {**goodman, 'md5sum': 'red', 'INSTCONF': 'Red', 'dateobs_center': '2018-03-01T03:00:00Z'},
            {**goodman, 'md5sum': 'blue', 'INSTCONF': 'Blue', 'dateobs_center': '2018-03-02T03:00:00Z'},
            # Before the red camera's first frame, every file is from the blue camera
            {**goodman, 'md5sum': 'early', 'dateobs_center': '2015-03-01T03:00:00Z'},
            # After it, a file that doesn't name its camera is given the red camera
            {**goodman, 'md5sum': 'unknown', 'dateobs_center': '2016-11-01T03:00:00Z'},
            # An image, which a spectroscopy search leaves out
            {**goodman, 'md5sum': 'image', 'INSTCONF': 'Red', 'GRATING': '<NO GRATING>',
             'dateobs_center': '2018-03-03T03:00:00Z'},
            {'md5sum': 'current', 'telescope': 'soar', 'instrument': 'ghts_red', 'proc_type': 'raw'},
            fields=NOIRLAB_FIELDS + NOIRLAB_GOODMAN_FIELDS,
        )
        query = {**self.query, 'start': datetime(2015, 1, 1).isoformat(), 'mode': 'spectroscopy'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        frames = self._search(response, 'noirlab')['frames']
        self.assertEqual({frame['id']: frame['instrument'] for frame in frames}, {
            'red': self.goodman_red.id,
            'blue': goodman_blue.id,
            'early': goodman_blue.id,
            'unknown': self.goodman_red.id,
            'current': self.goodman_red.id,
        })

    def test_selected_instruments_narrow_down_their_telescopes(self):
        query = {**self.query, 'telescopes': [self.tfn_1m.id, self.ogg_2m.id], 'instruments': [self.floyds.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._searched(response), {
            ('lco', 'imaging', (self.sinistro.id,)),
            ('lco', 'spectroscopy', (self.floyds.id,)),
        })

    def test_mode_limits_the_searches(self):
        query = {**self.query, 'telescopes': [self.gemini_north.id, self.ogg_2m.id], 'mode': 'spectroscopy'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(self._searched(response), {
            ('lco', 'spectroscopy', (self.floyds.id,)),
            ('gemini', 'spectroscopy', (self.gmos_n.id,)),
        })


class TestArchiveQueryResponse(BaseArchiveTestCase):
    def test_each_search_returns_its_frames_with_common_fields(self):
        self.lco.return_value.query_region.return_value = lco_table({})
        self.noirlab.return_value.query_metadata.return_value = noirlab_table({})
        self.gemini.return_value.query_raw.return_value = gemini_table({})
        query = {**self.query, 'instruments': [self.sinistro.id, self.decam.id, self.gmos_n.id], 'mode': 'imaging'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        searches = response.json()['searches']
        self.assertEqual(len(searches), 3)
        for search in searches:
            self.assertEqual(set(search), set(ArchiveSearchResultSerializer().fields))
            self.assertEqual(search['count'], 1)
            self.assertFalse(search['truncated'])
            self.assertIsNone(search['error'])
            frame = search['frames'][0]
            self.assertEqual(set(frame), set(ArchiveFrameSerializer().fields))
            # Every archive's frames come back with the same types, though Gemini's are all text
            self.assertIsInstance(frame['ra'], float)
            self.assertIsInstance(frame['exposure_time'], float)
            self.assertTrue(frame['observation_date'].endswith('Z'))
        self.assertEqual(self._search(response, 'lco')['frames'][0]['instrument'], self.sinistro.id)
        self.assertEqual(self._search(response, 'noirlab')['frames'][0]['target_name'], 'M101')
        self.assertEqual(self._search(response, 'gemini')['frames'][0]['url'],
                         'https://archive.gemini.edu/file/N20230605S0078.fits.bz2')

    def test_frames_beyond_the_row_limit_are_reported_as_truncated(self):
        # The archive returns the newest frames first
        self.lco.return_value.query_region.return_value = lco_table(
            *[{'id': i, 'observation_date': f'2024-03-0{i + 1}T00:00:00Z'} for i in reversed(range(3))]
        )
        query = {**self.query, 'instruments': [self.sinistro.id], 'row_limit': 2}
        response = self.client.get(reverse('api:archive-query'), data=query)
        search = self._search(response, 'lco')
        self.assertTrue(search['truncated'])
        self.assertEqual([frame['id'] for frame in search['frames']], ['2', '1'])

    def test_row_limit_applies_to_each_query_of_a_search(self):
        # An LCO imager that isn't selected, so each selected LCO imager is queried on its own
        tfn_0m4 = mixer.blend(models.Telescope, id='lco.tfn.aqwa-0m4a', site=self.tfn_1m.site, archive_id='0m4a')
        mixer.blend(models.Instrument, id='lco.tfn.aqwa-0m4a.sq32', telescope=tfn_0m4, archive_id='sq32',
                    supported_modes=[models.Instrument.SupportedModes.IMAGER])
        muscat = {'site_id': 'ogg', 'telescope_id': '2m0a', 'instrument_id': 'ep04'}
        self.lco.return_value.query_region.side_effect = [
            lco_table({'id': 1, 'observation_date': '2024-03-02T00:00:00Z', **muscat},
                      {'id': 2, 'observation_date': '2024-03-01T00:00:00Z', **muscat}),
            lco_table({'id': 3, 'observation_date': '2024-03-03T00:00:00Z'}),
        ]
        query = {**self.query, 'instruments': [self.sinistro.id, self.muscat.id], 'row_limit': 1}
        response = self.client.get(reverse('api:archive-query'), data=query)
        search = self._search(response, 'lco')
        self.assertTrue(search['truncated'])
        self.assertEqual([frame['id'] for frame in search['frames']], ['3', '1'])

    def test_gemini_frames_that_are_not_public_are_left_out(self):
        self.gemini.return_value.query_raw.return_value = gemini_table(
            {'data_label': 'public'},
            {'data_label': 'proprietary', 'release': '2999-01-01'},
            {'data_label': 'unknown', 'release': None},
        )
        query = {**self.query, 'instruments': [self.gmos_n.id], 'mode': 'imaging'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual([frame['id'] for frame in self._search(response, 'gemini')['frames']], ['public'])

    def test_failed_search_is_reported_without_failing_the_others(self):
        self.lco.return_value.query_region.side_effect = requests.exceptions.ReadTimeout('Read timed out')
        self.gemini.return_value.query_raw.return_value = gemini_table({})
        query = {**self.query, 'instruments': [self.sinistro.id, self.gmos_n.id], 'mode': 'imaging'}
        with self.assertLogs('heroic_api.archive', level='WARNING'):
            response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        lco_search = self._search(response, 'lco')
        self.assertEqual(lco_search['error'], 'The archive did not respond in time')
        self.assertEqual(lco_search['frames'], [])
        self.assertEqual(self._search(response, 'gemini')['count'], 1)

    def test_search_still_running_at_the_time_limit_is_reported(self):
        finish = threading.Event()
        self.addCleanup(finish.set)

        def slow_query(*args, **kwargs):
            finish.wait(10)
            return lco_table()

        self.lco.return_value.query_region.side_effect = slow_query
        self.gemini.return_value.query_raw.return_value = gemini_table({})
        query = {**self.query, 'instruments': [self.sinistro.id, self.gmos_n.id], 'mode': 'imaging'}
        with self.settings(ARCHIVE_QUERY_TIMEOUT=0.5):
            response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._search(response, 'lco')['error'], 'The search did not finish within 0.5 seconds')
        self.assertEqual(self._search(response, 'gemini')['count'], 1)

    def test_post_works_like_get(self):
        self.lco.return_value.query_region.return_value = lco_table({})
        query = {**self.query, 'instruments': [self.sinistro.id]}
        get_response = self.client.get(reverse('api:archive-query'), data=query)
        post_response = self.client.post(reverse('api:archive-query'), data=query, format='json')
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(get_response.json(), post_response.json())


class TestRubinPointingSearch(BaseArchiveTestCase):
    def _pointing(self, date, ra=RA, target='M101', planned=False, obs_id='MC_O_20240305_000001'):
        coordinate = Point(ra, DEC, srid=4326)
        return models.TelescopePointing.objects.create(
            date=datetime(*date, tzinfo=timezone.utc), telescope=self.rubin, instrument=self.lsstcam, target=target,
            planned=planned, coordinate=coordinate, field=coordinate.buffer(1.75),
            extra={'exposure_time': 30.0, 'obs_id': obs_id}
        )

    def test_performed_pointings_covering_the_position_are_found(self):
        self._pointing((2024, 3, 5))
        # A pointing whose field doesn't reach the position, a planned one, and one outside the date range
        self._pointing((2024, 3, 6), ra=RA + 10)
        self._pointing((2024, 3, 7), planned=True)
        self._pointing((2022, 3, 5))
        response = self.client.get(reverse('api:archive-query'), data={**self.query, 'instruments': [self.lsstcam.id]})
        self.assertEqual(response.status_code, 200)
        search = self._search(response, 'rubin')
        self.assertEqual(search['match'], 'exact')
        self.assertEqual(search['frames'], [{
            'id': 'MC_O_20240305_000001',
            'filename': None,
            'url': None,
            'observation_date': '2024-03-05T00:00:00Z',
            'ra': RA,
            'dec': DEC,
            'target_name': 'M101',
            'telescope': self.rubin.id,
            'instrument': self.lsstcam.id,
            'filter': None,
            'exposure_time': 30.0,
            'observation_type': None,
            'reduction_level': None,
            'processed': False,
            'proposal_id': None,
            'public_date': None,
        }])

    def test_performed_pointings_are_found_by_target_name(self):
        self._pointing((2024, 3, 5), obs_id='first')
        # The name matches whatever the position, ignoring case
        self._pointing((2024, 3, 6), ra=RA + 10, target='m101', obs_id='second')
        self._pointing((2024, 3, 7), target='M51')
        query = {'target_name': 'M101', 'start': self.query['start'], 'end': self.query['end'],
                 'instruments': [self.lsstcam.id]}
        response = self.client.get(reverse('api:archive-query'), data=query)
        search = self._search(response, 'rubin')
        self.assertEqual(search['match'], 'name')
        self.assertEqual([frame['id'] for frame in search['frames']], ['second', 'first'])

    def test_processed_searches_find_no_pointings(self):
        self._pointing((2024, 3, 5))
        query = {**self.query, 'instruments': [self.lsstcam.id], 'reduction_level': 'processed'}
        response = self.client.get(reverse('api:archive-query'), data=query)
        self.assertEqual(response.status_code, 200)
        search = self._search(response, 'rubin')
        self.assertIsNone(search['error'])
        self.assertEqual(search['frames'], [])
