from rest_framework.test import APITestCase
from mixer.backend.django import mixer
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime

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


class TestVisibilityAirmass(BaseVisibilityTestCase):
    def test_visibility_airmasses_basic_icrs_succeeds(self):
        query = self.m22_basic_target_query.copy()
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 18)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T17:29:09.080298+00:00', '2025-03-01T17:39:09.080298+00:00',
                          '2025-03-01T17:49:09.080298+00:00', '2025-03-01T17:59:09.080298+00:00'],
                'airmasses': [1.9987162221252022, 1.8809851094809273, 1.778227573468417, 1.6879817282310983]
            }
        }
        response = self.client.get(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_airmasses, airmasses)

    def test_visibility_airmasses_basic_icrs_succeeds_with_post(self):
        query = self.m22_basic_target_query.copy()
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 18)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T17:29:09.080298+00:00', '2025-03-01T17:39:09.080298+00:00',
                          '2025-03-01T17:49:09.080298+00:00', '2025-03-01T17:59:09.080298+00:00'],
                'airmasses': [1.9987162221252022, 1.8809851094809273, 1.778227573468417, 1.6879817282310983]
            }
        }
        response = self.client.post(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_airmasses, airmasses)

    def test_visibility_airmasses_minor_planet_succeeds(self):
        query = self.minor_planet_target_query
        # constrain query so our expected values are shorter
        query['telescopes'] = [self.telescope.id]
        query['end'] = datetime(2025, 3, 1, 10)
        expected_airmasses = {
            self.telescope.id: {
                'times': ['2025-03-01T09:31:42.339675+00:00', '2025-03-01T09:41:42.339675+00:00',
                          '2025-03-01T09:51:42.339675+00:00'],
                'airmasses': [1.7703200219302355, 1.7567105747821408, 1.7478200356418352]
            }
        }
        response = self.client.get(reverse('api:visibility-airmass'), data=query)
        airmasses = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected_airmasses, airmasses)
