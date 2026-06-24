from rest_framework.test import APITestCase
from mixer.backend.django import mixer
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime, timezone
import numpy as np

from heroic_api import models


class BaseVisibilityTestCase(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, id='tstObs', admin=self.user)
        self.site = mixer.blend(models.Site, id=f'{self.observatory.id}.coj', observatory=self.observatory, elevation=3000)
        self.telescope = mixer.blend(models.Telescope, id=f'{self.site.id}.2m0a', site=self.site,
                                     latitude=-31.272932, longitude=149.070648, horizon=15.0,
                                     positive_ha_limit=4.6, negative_ha_limit=-4.6, aperture=2.0)
        self.site2 = mixer.blend(models.Site, id=f'{self.observatory.id}.lsc', observatory=self.observatory, elevation=3000)
        self.telescope2 = mixer.blend(models.Telescope, id=f'{self.site2.id}.1m0a', site=self.site2,
                                     latitude=-30.1674472222, longitude=-70.8046805556, horizon=15.0,
                                     positive_ha_limit=4.6, negative_ha_limit=-4.6, aperture=1.0)
        # M22 ra/dec
        self.m22_basic_target_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'ra': 279.09975,
            'dec': -23.90475,
            'max_airmass': 2
        }
        # M22 full ICRS
        self.m22_full_target_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'ra': 279.09975,
            'dec': -23.90475,
            'proper_motion_ra': 9.82,
            'proper_motion_dec': -5.54,
            'parallax': 0.306,
            'max_airmass': 2
        }
        # MPC 19255        
        self.minor_planet_target_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'epoch_of_elements': 59600,
            'orbital_inclination': 1.48467,
            'longitude_of_ascending_node': 72.3357657,
            'argument_of_perihelion': 119.49807,
            'eccentricity': 0.0306641,
            'mean_distance': 42.69391,
            'mean_anomaly': 267.71107,
            'max_airmass': 2
        }
        # MPC PJ99R28O        
        self.comet_target_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'epoch_of_elements': 56400,
            'orbital_inclination': 8.18884,
            'longitude_of_ascending_node': 148.3155371,
            'argument_of_perihelion': 220.09003,
            'eccentricity': 0.6529808,
            'perihelion_distance': 1.2193886,
            'epoch_of_perihelion': 56278.58647,
            'max_airmass': 2
        }
        self.mars_target_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'epoch_of_elements': 60181,
            'orbital_inclination': 1.847919327404603,
            'longitude_of_ascending_node': 49.48984370080841,
            'argument_of_perihelion': 286.6396041587725,
            'eccentricity': 0.09334416606027193,
            'mean_distance': 1.52369752919589,
            'mean_anomaly': 225.1309151389929,
            'daily_motion': 0.5240298172661463,
            'max_airmass': 2
        }

class TestVisibilityIntervals(BaseVisibilityTestCase):
    def test_visibility_intervals_basic_icrs_succeeds(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T17:29:09.080298Z', '2025-03-01T19:00:37.291560Z']],
            self.telescope2.id: [['2025-03-01T08:11:29.401273Z', '2025-03-01T09:41:16.314638Z']]
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=self.m22_basic_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_basic_icrs_succeeds_with_post(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T17:29:09.080298Z', '2025-03-01T19:00:37.291560Z']],
            self.telescope2.id: [['2025-03-01T08:11:29.401273Z', '2025-03-01T09:41:16.314638Z']]
        }
        response = self.client.post(reverse('api:visibility-intervals'), data=self.m22_basic_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_full_icrs_succeeds(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T17:29:09.114194Z', '2025-03-01T19:00:37.291560Z']],
            self.telescope2.id: [['2025-03-01T08:11:29.435316Z', '2025-03-01T09:41:16.314638Z']]
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=self.m22_full_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_minor_planet_succeeds(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T09:31:42.339675Z', '2025-03-01T11:45:00Z']],
            self.telescope2.id: [['2025-03-01T00:10:10.226436Z', '2025-03-01T02:30:00Z']]
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=self.minor_planet_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_comet_succeeds(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T16:15:00Z', '2025-03-01T19:00:37.291560Z']],
            self.telescope2.id: [['2025-03-01T07:00:00Z', '2025-03-01T09:41:16.314638Z']]
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=self.comet_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_major_planet_succeeds(self):
        expected_intervals = {
            self.telescope.id: [['2025-03-01T09:31:42.339675Z', '2025-03-01T11:45:00Z']],
            self.telescope2.id: [['2025-03-01T00:10:10.226436Z', '2025-03-01T02:45:00Z']]
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=self.mars_target_query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_filter_telescope_id(self):
        query = self.m22_basic_target_query.copy()
        query['telescopes'] = [self.telescope.id]
        expected_intervals = {
            self.telescope.id: [['2025-03-01T17:29:09.080298Z', '2025-03-01T19:00:37.291560Z']],
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_filter_airmass(self):
        query = self.m22_basic_target_query.copy()
        query['max_airmass'] = 1
        # There are no intervals with airmass of 1 for this target
        expected_intervals = {
            self.telescope.id: [],
            self.telescope2.id: []
        }
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        intervals = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_intervals, intervals)

    def test_visibility_intervals_dates_required(self):
        query = self.m22_basic_target_query.copy()
        del query['start']
        del query['end']
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn('start', response.json())
        self.assertIn('end', response.json())

    def test_visibility_intervals_target_required(self):
        query = self.m22_basic_target_query.copy()
        del query['ra']
        del query['dec']
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        self.assertContains(response, 'a valid target using either ra/dec', status_code=400)

    def test_visibility_intervals_minor_planet_target_missing_fields(self):
        query = self.minor_planet_target_query.copy()
        del query['mean_distance']
        del query['orbital_inclination']
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn('mean_distance', response.json())
        self.assertIn('orbital_inclination', response.json())

    def test_visibility_intervals_major_planet_target_missing_fields(self):
        query = self.mars_target_query.copy()
        del query['eccentricity']
        del query['orbital_inclination']
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn('eccentricity', response.json())
        self.assertIn('orbital_inclination', response.json())

    def test_visibility_intervals_respects_past_telescope_status(self):
        query = self.m22_basic_target_query.copy()
        query['end'] = datetime(2025, 3, 10).isoformat()
        query['telescopes'] = [self.telescope.id]
        query['include_status'] = True
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        # Check that there is 2025-03-04/5/6 in the visibility intervals somewhere
        self.assertContains(response, '2025-03-04T', status_code=200)
        self.assertContains(response, '2025-03-05T', status_code=200)
        self.assertContains(response, '2025-03-06T', status_code=200)

        # Now create an old status blocking out 2025-03-05 and verify it gets blocked out
        mixer.blend(models.TelescopeStatus, date=datetime(2025, 3, 5, tzinfo=timezone.utc), telescope=self.telescope, status=models.TelescopeStatus.StatusChoices.UNAVAILABLE)
        mixer.blend(models.TelescopeStatus, date=datetime(2025, 3, 6, tzinfo=timezone.utc), telescope=self.telescope, status=models.TelescopeStatus.StatusChoices.AVAILABLE)
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        # Check that there is no longer 2025-03-05 in the visibility intervals
        self.assertContains(response, '2025-03-04T', status_code=200)
        self.assertNotContains(response, '2025-03-05T', status_code=200)
        self.assertContains(response, '2025-03-06T', status_code=200)

    def test_visibility_intervals_respects_past_instrument_status(self):
        query = self.m22_basic_target_query.copy()
        query['end'] = datetime(2025, 3, 10).isoformat()
        query['telescopes'] = [self.telescope.id]
        query['include_status'] = True
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        # Check that there is 2025-03-04/5/6 in the visibility intervals somewhere
        self.assertContains(response, '2025-03-04T', status_code=200)
        self.assertContains(response, '2025-03-05T', status_code=200)
        self.assertContains(response, '2025-03-06T', status_code=200)

        # Now create an old instrument and status blocking out 2025-03-05 and verify it gets blocked out
        instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        mixer.blend(models.InstrumentCapability, instrument=instrument, date=datetime(2025, 2, 1, tzinfo=timezone.utc), status=models.InstrumentCapability.InstrumentStatus.AVAILABLE)
        mixer.blend(models.InstrumentCapability, instrument=instrument, date=datetime(2025, 3, 5, tzinfo=timezone.utc), status=models.InstrumentCapability.InstrumentStatus.UNAVAILABLE)
        mixer.blend(models.InstrumentCapability, instrument=instrument, date=datetime(2025, 3, 6, tzinfo=timezone.utc), status=models.InstrumentCapability.InstrumentStatus.AVAILABLE)

        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        # Check that there is no longer 2025-03-05 in the visibility intervals
        self.assertContains(response, '2025-03-04T', status_code=200)
        self.assertNotContains(response, '2025-03-05T', status_code=200)
        self.assertContains(response, '2025-03-06T', status_code=200)

        # Now create a second instrument that is always available and see that 2025-03-05 has visibility again
        instrument2 = mixer.blend(models.Instrument, telescope=self.telescope)
        mixer.blend(models.InstrumentCapability, instrument=instrument2, date=datetime(2025, 2, 1, tzinfo=timezone.utc), status=models.InstrumentCapability.InstrumentStatus.AVAILABLE)
        response = self.client.get(reverse('api:visibility-intervals'), data=query)
        # Check that there is 2025-03-04/5/6 in the visibility intervals somewhere
        self.assertContains(response, '2025-03-04T', status_code=200)
        self.assertContains(response, '2025-03-05T', status_code=200)
        self.assertContains(response, '2025-03-06T', status_code=200)


class TestVisibilityAirmass(BaseVisibilityTestCase):
    def _compare_airmasses(self, expected_airmasses, actual_airmasses):
        for telescope in set(list(expected_airmasses.keys()) + list(actual_airmasses.keys())):
            expected = expected_airmasses.get(telescope, {})
            actual = actual_airmasses.get(telescope, {})
            self.assertEqual(expected.get('times', []), actual.get('times', []))
            self.assertEqual(len(expected.get('airmasses', [])), len(actual.get('airmasses', [])))
            for i, airmass in enumerate(expected.get('airmasses', [])):
                self.assertAlmostEqual(airmass, actual['airmasses'][i], 7)

    def test_visibility_airmasses_basic_icrs_succeeds(self):
        query = self.m22_basic_target_query.copy()
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 18)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T17:29:09.080298', '2025-03-01T17:39:09.080298',
                          '2025-03-01T17:49:09.080298', '2025-03-01T17:59:09.080298'],
                'airmasses': [1.9987162221252013, 1.8809851094809273, 1.7782275734684165, 1.6879817282310978]
            }
        }
        response = self.client.get(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self._compare_airmasses(expected_airmasses, airmasses)

    def test_visibility_airmasses_basic_icrs_succeeds_with_post(self):
        query = self.m22_basic_target_query.copy()
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 18)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T17:29:09.080298', '2025-03-01T17:39:09.080298',
                          '2025-03-01T17:49:09.080298', '2025-03-01T17:59:09.080298'],
                'airmasses': [1.9987162221252013, 1.8809851094809273, 1.7782275734684165, 1.6879817282310978]
            }
        }
        response = self.client.post(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self._compare_airmasses(expected_airmasses, airmasses)

    def test_visibility_airmasses_minor_planet_succeeds(self):
        query = self.minor_planet_target_query
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 10)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T09:31:42.339675', '2025-03-01T09:41:42.339675',
                          '2025-03-01T09:51:42.339675'],
                'airmasses': [1.7703200219302353, 1.7567105747821412, 1.7478200356418352]
            }
        }
        response = self.client.get(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self._compare_airmasses(expected_airmasses, airmasses)


class TestSkyMapVisibility(BaseVisibilityTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.skymap_query = {
            'start': datetime(2025, 3, 1).isoformat(),
            'end': datetime(2025, 3, 2).isoformat(),
            'nside': 32,
        }

    def _assert_valid_binned_moc(self, entry, expected_nside, expected_bins):
        """Assert a per-telescope entry is a well-formed binned MOC."""
        from mocpy import MOC
        expected_order = str(int(np.log2(expected_nside)))
        self.assertEqual(entry['max_order'], int(expected_order))
        self.assertEqual(entry['num_bins'], expected_bins)
        # Every bin key is an upper bound in (0, 1] aligned to the bin width,
        # and each bin is order-keyed json that round-trips through MOCpy.
        valid_upper_bounds = {f'{(i + 1) / expected_bins:.2f}' for i in range(expected_bins)}
        for upper_bound, moc_json in entry['moc'].items():
            self.assertIn(upper_bound, valid_upper_bounds)
            self.assertGreater(len(moc_json), 0)
            for order, ipix in moc_json.items():
                self.assertIsInstance(ipix, list)
                # MOC compaction can roll cells up, but never below the map order
                self.assertLessEqual(int(order), int(expected_order))
            # round-trips back into a usable MOC
            self.assertIsInstance(MOC.from_json(moc_json), MOC)

    def test_skymap_binned_moc_succeeds(self):
        query = self.skymap_query.copy()
        query['telescopes'] = [self.telescope.id]
        query['bins'] = 4
        response = self.client.get(reverse('api:visibility-skymap'), data=query)
        self.assertEqual(response.status_code, 200)
        skymap_by_telescope = response.json()
        self.assertEqual(list(skymap_by_telescope.keys()), [self.telescope.id])
        entry = skymap_by_telescope[self.telescope.id]
        self._assert_valid_binned_moc(entry, expected_nside=32, expected_bins=4)
        # A telescope sees a good fraction of the sky over a full day, so at
        # least one visibility bin should contain cells.
        self.assertTrue(any(entry['moc'].values()))

    def test_skymap_binned_moc_defaults_to_ten_bins(self):
        query = self.skymap_query.copy()
        query['telescopes'] = [self.telescope.id]
        response = self.client.get(reverse('api:visibility-skymap'), data=query)
        self.assertEqual(response.status_code, 200)
        entry = response.json()[self.telescope.id]
        self._assert_valid_binned_moc(entry, expected_nside=32, expected_bins=10)

    def test_skymap_filters_to_requested_telescope(self):
        query = self.skymap_query.copy()
        query['telescopes'] = [self.telescope2.id]
        response = self.client.get(reverse('api:visibility-skymap'), data=query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.json().keys()), [self.telescope2.id])

    def test_skymap_all_telescopes_when_none_specified(self):
        response = self.client.get(reverse('api:visibility-skymap'), data=self.skymap_query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json().keys()), {self.telescope.id, self.telescope2.id})

    def test_skymap_end_before_start_fails(self):
        query = self.skymap_query.copy()
        query['start'], query['end'] = query['end'], query['start']
        response = self.client.get(reverse('api:visibility-skymap'), data=query)
        self.assertEqual(response.status_code, 400)
        self.assertIn('end', response.json())
