from rest_framework.test import APITestCase
from mixer.backend.django import mixer
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from heroic_api import models


class TestCreateApi(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, id='tstObs', admin=self.user)
        self.site = mixer.blend(models.Site, id=f'{self.observatory.id}.testSite', observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, id=f'{self.site.id}.testTel', site=self.site)

    def test_create_observatory_works_for_superuser(self):
        superuser = mixer.blend(User, is_superuser=True, is_staff=True)
        self.client.force_login(superuser)
        observatory = {'id': 'LCO', 'name': 'Las Cumbres Observatory'}
        response = self.client.post(reverse('api:observatory-list'), data=observatory)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], observatory['name'])
        self.assertEqual(response.json()['id'], observatory['id'])

    def test_create_observatory_with_non_superuser_fails(self):
        observatory = {'id': 'LCO', 'name': 'Las Cumbres Observatory'}
        response = self.client.post(reverse('api:observatory-list'), data=observatory)
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_observatory_without_authentication_fails(self):
        self.client.logout()
        observatory = {'id': 'LCO', 'name': 'Las Cumbres Observatory'}
        response = self.client.post(reverse('api:observatory-list'), data=observatory)
        self.assertContains(response, 'Authentication credentials were not provided', status_code=403)

    def test_create_site(self):
        site = {'id': f'{self.observatory.id}.tst', 'name': 'Test Site', 'observatory': self.observatory.id,
                'elevation': 1000.0}
        response = self.client.post(reverse('api:site-list'), data=site)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], site['name'])
        self.assertEqual(response.json()['id'], site['id'])
        self.assertEqual(response.json()['observatory'], self.observatory.id)

    def test_create_site_fails_with_invalid_id(self):
        site = {'id': f'notMyObs.tst', 'name': 'Test Site', 'observatory': self.observatory.id,
                'elevation': 1000.0}
        response = self.client.post(reverse('api:site-list'), data=site)
        self.assertContains(response, 'Site id must follow the format', status_code=400)

        site = {'id': f'tst', 'name': 'Test Site', 'observatory': self.observatory.id,
                'elevation': 1000.0}
        response = self.client.post(reverse('api:site-list'), data=site)
        self.assertContains(response, 'Site id must follow the format', status_code=400)

    def test_create_site_with_non_admin_user_fails(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        site = {'id': 'tst', 'name': 'Test Site', 'observatory': self.observatory.id,
                'elevation': 1000.0}
        response = self.client.post(reverse('api:site-list'), data=site)
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_telescope(self):
        telescope = {'id': f'{self.site.id}.1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482}
        response = self.client.post(reverse('api:telescope-list'), data=telescope)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], telescope['name'])
        self.assertEqual(response.json()['id'], telescope['id'])
        self.assertEqual(response.json()['site'], self.site.id)
        # With no status, the default unavailable is returned as status
        self.assertEqual(response.json()['status'], models.TelescopeStatus.StatusChoices.UNAVAILABLE)
        self.assertEqual(response.json()['reason'], '')
        self.assertEqual(response.json()['extra'], {})

    def test_create_telescope_with_non_admin_user_fails(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        telescope = {'id': '1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482}
        response = self.client.post(reverse('api:telescope-list'), data=telescope)
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_telescope_with_status(self):
        telescope = {'id': f'{self.site.id}.1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482,
                     'status': models.TelescopeStatus.StatusChoices.SCHEDULABLE,
                     'extra': {'operator': 'Mr. Bean'}}
        response = self.client.post(reverse('api:telescope-list'), data=telescope, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], telescope['name'])
        self.assertEqual(response.json()['id'], telescope['id'])
        self.assertEqual(response.json()['site'], self.site.id)
        self.assertEqual(response.json()['status'], telescope['status'])
        self.assertEqual(response.json()['extra'], telescope['extra'])

    def test_create_telescope_fails_with_invalid_id(self):
        telescope = {'id': f'testObs.NotSite.1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482}
        response = self.client.post(reverse('api:telescope-list'), data=telescope)
        self.assertContains(response, 'Telescope id must follow the format', status_code=400)

        telescope = {'id': f'1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482}
        response = self.client.post(reverse('api:telescope-list'), data=telescope)
        self.assertContains(response, 'Telescope id must follow the format', status_code=400)

    def test_create_instrument(self):
        instrument = {'id': f'{self.telescope.id}.fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id}
        response = self.client.post(reverse('api:instrument-list'), data=instrument)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], instrument['name'])
        self.assertEqual(response.json()['id'], instrument['id'])
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        # With no capability, the default unavailable is returned as status
        self.assertEqual(response.json()['status'], models.InstrumentCapability.InstrumentStatus.UNAVAILABLE)
        self.assertEqual(response.json()['operation_modes'], {})
        self.assertEqual(response.json()['optical_element_groups'], {})

    def test_create_instrument_with_non_admin_user_fails(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        instrument = {'id': 'fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id}
        response = self.client.post(reverse('api:instrument-list'), data=instrument)
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_instrument_with_capabilities(self):
        instrument = {'id': f'{self.telescope.id}.fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id,
                      'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'operation_modes': {'readout': {'default': 'full-frame', 'options': [{'id': 'full-frame', 'name': 'Full Frame Readout Mode'}]}}}
        response = self.client.post(reverse('api:instrument-list'), data=instrument, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], instrument['name'])
        self.assertEqual(response.json()['id'], instrument['id'])
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        self.assertEqual(response.json()['status'], instrument['status'])
        self.assertEqual(response.json()['operation_modes'], instrument['operation_modes'])

    def test_create_instrument_fails_with_invalid_id(self):
        instrument = {'id': f'testObs.testSite.NotATel.fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id}
        response = self.client.post(reverse('api:instrument-list'), data=instrument)
        self.assertContains(response, 'Instrument id must follow the format', status_code=400)

        instrument = {'id': f'fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id}
        response = self.client.post(reverse('api:instrument-list'), data=instrument)
        self.assertContains(response, 'Instrument id must follow the format', status_code=400)


class TestTelescopePointing(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, admin=self.user, id='observatory')
        self.site = mixer.blend(models.Site, observatory=self.observatory, id='observatory.site')
        self.telescope = mixer.blend(models.Telescope, site=self.site, id='observatory.site.tel1')
        self.other_telescope = mixer.blend(models.Telescope, site=self.site, id='observatory.site.tel2')
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope, id='observatory.site.tel1.inst1')
        self.other_instrument = mixer.blend(models.Instrument, telescope=self.other_telescope, id='observatory.site.tel2.inst1')
        self.test_pointing = {
            'telescope': self.telescope.id,
            'target': 'Test Target',
            'instrument': self.instrument.id,
            'ra': 114.4,
            'dec': 45.54,
            'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
        }

    def test_create_telescope_pointing(self):
        response = self.client.post(reverse('api:telescopepointing-list'), data=self.test_pointing, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], self.test_pointing['telescope'])
        self.assertEqual(response.json()['ra'], self.test_pointing['ra'])
        self.assertEqual(response.json()['dec'], self.test_pointing['dec'])
        self.assertEqual(response.json()['extra'], self.test_pointing['extra'])
        self.assertEqual(response.json()['target'], self.test_pointing['target'])
        self.assertEqual(response.json()['instrument'], self.test_pointing['instrument'])

    def test_create_telescope_pointing_in_past(self):
        pointing = self.test_pointing.copy()
        pointing['date'] = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['date'], pointing['date'].replace('+00:00', 'Z'))

    def test_create_telescope_pointing_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        response = self.client.post(reverse('api:telescopepointing-list'), data=self.test_pointing, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_telescope_pointing_fails_if_instrument_isnt_on_telescope(self):
        pointing = self.test_pointing.copy()
        pointing['instrument'] = self.other_instrument.id
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Instrument {self.other_instrument.id} is not on Telescope {self.telescope.id}', status_code=400)

    def test_create_telescope_pointing_fails_if_instrument_doesnt_exist(self):
        pointing = self.test_pointing.copy()
        instrument_id = f'{self.telescope.id}.NotAnInstrument'
        pointing['instrument'] = instrument_id
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Invalid pk \\"{instrument_id}\\"', status_code=400)

    def test_create_telescope_pointing_fails_if_telescope_doesnt_exist(self):
        pointing = self.test_pointing.copy()
        telescope_id = f'{".".join(self.telescope.id.split(".")[:-1])}.NotATelescope'
        pointing['telescope'] = telescope_id
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Invalid pk \\"{telescope_id}\\"', status_code=400)

    def test_create_telescope_status_fails_if_date_in_future(self):
        pointing = self.test_pointing.copy()
        pointing['date'] = (timezone.now() + timedelta(days=1)).isoformat()
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, 'Date cannot be in the future', status_code=400)

    def test_create_telescope_pointing_fails_if_ra_out_of_range(self):
        pointing = self.test_pointing.copy()
        pointing['ra'] = -123.3
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Ensure this value is greater than or equal to 0.0', status_code=400)

        pointing['ra'] = 361.0
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Ensure this value is less than or equal to 360.0', status_code=400)

    def test_create_telescope_pointing_fails_if_dec_out_of_range(self):
        pointing = self.test_pointing.copy()
        pointing['dec'] = -91.1
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Ensure this value is greater than or equal to -90.0', status_code=400)

        pointing['dec'] = 91.1
        response = self.client.post(reverse('api:telescopepointing-list'), data=pointing, format='json')
        self.assertContains(response, f'Ensure this value is less than or equal to 90.0', status_code=400)


class TestTelescopeStatus(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, admin=self.user)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.telescope_status = mixer.blend(models.TelescopeStatus, telescope=self.telescope, date=timezone.now(),
                                            reason='Initial', extra={'key': 'test'})

    def _create_telescope_status(self, status):
        response = self.client.post(reverse('api:telescopestatus-list'), data=status, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], status['telescope'])
        self.assertEqual(response.json()['status'], status['status'])
        if 'extra' in status:
            self.assertEqual(response.json()['extra'], status['extra'])

    def test_create_telescope_status(self):
        # Get the telescope and see that the base status is blended in
        response = self.client.get(reverse('api:telescope-detail', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], self.telescope_status.status)
        self.assertEqual(response.json()['reason'], self.telescope_status.reason)
        self.assertEqual(response.json()['extra'], self.telescope_status.extra)
        # Now set a new status on the telescope
        status = {'telescope': self.telescope.id,
                  'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        self._create_telescope_status(status)
        # Now get the telescope and see that this status is blended in
        response = self.client.get(reverse('api:telescope-detail', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['reason'], status['reason'])
        self.assertEqual(response.json()['extra'], status['extra'])

    def test_create_telescope_status_in_past(self):
        # Now set a status on the telescope in the past
        status = {'telescope': self.telescope.id,
                  'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'date': (timezone.now() - timedelta(days=30)).isoformat(),
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        self._create_telescope_status(status)

    def test_create_telescope_status_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        status = {'telescope': self.telescope.id,
                  'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        response = self.client.post(reverse('api:telescopestatus-list'), data=status, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_telescope_status_fails_if_date_in_future(self):
        status = {'telescope': self.telescope.id,
                  'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'date': (timezone.now() + timedelta(days=1)).isoformat(),
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        response = self.client.post(reverse('api:telescopestatus-list'), data=status, format='json')
        self.assertContains(response, 'Date cannot be in the future', status_code=400)

    def test_fails_to_create_telescope_status_from_telescope_endpoint(self):
        # Set telescope status without telescope id, that is part of the endpoint instead
        status = {'status': 'Not a Status',
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        response = self.client.post(reverse('api:telescope-status', args=(self.telescope.id,)), data=status, format='json')
        self.assertContains(response, 'Not a Status', status_code=400)

    def test_create_telescope_status_from_telescope_endpoint(self):
        # Set telescope status without telescope id, that is part of the endpoint instead
        status = {'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        response = self.client.post(reverse('api:telescope-status', args=(self.telescope.id,)), data=status, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['reason'], status['reason'])
        self.assertEqual(response.json()['extra'], status['extra'])

    def test_create_telescope_status_from_telescope_endpoint_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        status = {'status': models.TelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'}
                  }
        response = self.client.post(reverse('api:telescope-status', args=(self.telescope.id,)), data=status, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_getting_all_telescope_statuses_for_telescope(self):
        self.client.logout()
        # Add a second telescope status
        second_status = mixer.blend(models.TelescopeStatus, telescope=self.telescope, date=timezone.now(),
                                    reason='Second', status=models.TelescopeStatus.StatusChoices.UNAVAILABLE)
        # Test that two telescope statuses are received in latest date order
        response = self.client.get(reverse('api:telescope-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        latest_status = response.json()[0]
        self.assertEqual(latest_status['status'], second_status.status)
        self.assertEqual(latest_status['reason'], second_status.reason)
        first_status = response.json()[1]
        self.assertEqual(first_status['status'], self.telescope_status.status)
        self.assertEqual(first_status['reason'], self.telescope_status.reason)


class TestPlannedTelescopeStatus(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, admin=self.user)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.telescope_status = mixer.blend(models.TelescopeStatus, telescope=self.telescope, date=timezone.now(),
                                            reason='Initial', extra={'key': 'test'},
                                            status=models.PlannedTelescopeStatus.StatusChoices.SCHEDULABLE)
        self.planned_telescope_status = mixer.blend(models.PlannedTelescopeStatus, telescope=self.telescope,
                                                    status=models.PlannedTelescopeStatus.StatusChoices.UNAVAILABLE,
                                                    start=timezone.now() + timedelta(days=30),
                                                    end=timezone.now() + timedelta(days=37),
                                                    reason='Engineering', extra={'key': 'test'})

    def _create_planned_telescope_status(self, status):
        response = self.client.post(reverse('api:plannedtelescopestatus-list'), data=status, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], status['telescope'])
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['start'], status['start'].replace("+00:00", "Z"))
        self.assertEqual(response.json()['end'], status['end'].replace("+00:00", "Z"))
        if 'extra' in status:
            self.assertEqual(response.json()['extra'], status['extra'])


    def test_create_planned_telescope_status(self):
        # Set a new planned status on the telescope
        status = {'telescope': self.telescope.id,
                  'status': models.PlannedTelescopeStatus.StatusChoices.AVAILABLE,
                  'reason': 'Engineering Night',
                  'start': (timezone.now() + timedelta(days=4)).isoformat(),
                  'end': (timezone.now() + timedelta(days=5)).isoformat()
                  }
        self._create_planned_telescope_status(status)
        # Now get the telescope planned status from the telescope endpoint
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]['status'], status['status'])
        self.assertEqual(response.json()[0]['reason'], status['reason'])
        self.assertEqual(response.json()[0]['extra'], {})

    def test_create_planned_telescope_status_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        status = {'telescope': self.telescope.id,
                  'status': models.PlannedTelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'start': (timezone.now() + timedelta(days=4)).isoformat(),
                  'end': (timezone.now() + timedelta(days=5)).isoformat()
                  }
        response = self.client.post(reverse('api:plannedtelescopestatus-list'), data=status, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_planned_telescope_status_from_telescope_endpoint(self):
        # Set planned telescope status without telescope id, that is part of the endpoint instead
        status = {'status': models.PlannedTelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'start': (timezone.now() + timedelta(days=4)).isoformat(),
                  'end': (timezone.now() + timedelta(days=5)).isoformat()
                  }
        response = self.client.post(reverse('api:telescope-planned-status', args=(self.telescope.id,)), data=status, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['reason'], status['reason'])
        self.assertEqual(response.json()['extra'], {})

    def test_create_planned_telescope_status_from_telescope_endpoint_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        status = {'status': models.PlannedTelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'start': (timezone.now() + timedelta(days=4)).isoformat(),
                  'end': (timezone.now() + timedelta(days=5)).isoformat()
                  }
        response = self.client.post(reverse('api:telescope-planned-status', args=(self.telescope.id,)), data=status, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_planned_telescope_status_fails_if_end_before_start(self):
        status = {'telescope': self.telescope.id,
                  'status': models.PlannedTelescopeStatus.StatusChoices.UNAVAILABLE,
                  'reason': 'Engineering Night',
                  'end': (timezone.now() + timedelta(days=4)).isoformat(),
                  'start': (timezone.now() + timedelta(days=5)).isoformat()
                  }
        response = self.client.post(reverse('api:plannedtelescopestatus-list'), data=status, format='json')
        self.assertContains(response, 'The end datetime must be greater than or equal to the start datetime', status_code=400)

    def test_getting_all_planned_telescope_statuses_for_telescope(self):
        self.client.logout()
        # Add a second planned telescope status
        second_status = mixer.blend(models.PlannedTelescopeStatus, telescope=self.telescope, start=(timezone.now() + timedelta(days=4)),
                                    end=(timezone.now() + timedelta(days=5)),
                                    reason='Second', status=models.TelescopeStatus.StatusChoices.UNAVAILABLE)
        # Test that two planned telescope statuses are received in ascending start date order
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        latest_status = response.json()[0]
        self.assertEqual(latest_status['status'], second_status.status)
        self.assertEqual(latest_status['reason'], second_status.reason)
        self.assertEqual(latest_status['start'], second_status.start.isoformat().replace("+00:00", "Z"))
        first_status = response.json()[1]
        self.assertEqual(first_status['status'], self.planned_telescope_status.status)
        self.assertEqual(first_status['reason'], self.planned_telescope_status.reason)
        self.assertEqual(first_status['start'],  self.planned_telescope_status.start.isoformat().replace("+00:00", "Z"))

    def test_delete_planned_telescope_status(self):
        status_id = self.planned_telescope_status.id
        response = self.client.delete(reverse('api:plannedtelescopestatus-detail', args=(status_id,)))
        self.assertEqual(response.status_code, 204)
        # Now check that that planned telescope status no longer exists
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_delete_planned_telescope_status_fails_if_not_admin_user(self):
        status_id = self.planned_telescope_status.id
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        response = self.client.delete(reverse('api:plannedtelescopestatus-detail', args=(status_id,)))
        self.assertContains(response, 'You do not have permission', status_code=403)
        # Now check that that planned telescope status still exists
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_update_planned_telescope_status_fields(self):
        status_id = self.planned_telescope_status.id
        old_start = self.planned_telescope_status.start
        # Check that that planned telescope status start time is the old_start
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['start'], old_start.isoformat().replace("+00:00", "Z"))
        # Now patch update to a new start time
        new_start = old_start - timedelta(days=20)
        new_end = new_start + timedelta(days=7)
        update = {
            'start': new_start.isoformat(),
            'end': new_end.isoformat()
        }
        response = self.client.patch(reverse('api:plannedtelescopestatus-detail', args=(status_id,)), data=update, format='json')
        self.assertEqual(response.status_code, 200)
        # Now check that that planned telescope status exists and its start time is the new_start
        response = self.client.get(reverse('api:telescope-planned-status', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['start'], new_start.isoformat().replace("+00:00", "Z"))
        self.assertEqual(response.json()[0]['end'], new_end.isoformat().replace("+00:00", "Z"))


class TestInstrumentCapability(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, admin=self.user)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.instrument_capability = mixer.blend(models.InstrumentCapability, instrument=self.instrument,
                                                 date=timezone.now(),
                                                 status=models.InstrumentCapability.InstrumentStatus.AVAILABLE,
                                                 optical_element_groups={'filters': {}},
                                                 operation_modes={'readout': {}}
                                                )

    def _create_instrument_capability(self, capability):
        response = self.client.post(reverse('api:instrumentcapability-list'), data=capability, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['instrument'], capability['instrument'])
        self.assertEqual(response.json()['status'], capability['status'])
        self.assertEqual(response.json()['optical_element_groups'], capability.get('optical_element_groups', {}))
        self.assertEqual(response.json()['operation_modes'], capability.get('operation_modes', {}))

    def test_create_instrument_capability(self):
        # Get the instrument and see that the base capability is blended in
        response = self.client.get(reverse('api:instrument-detail', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], self.instrument_capability.status)
        self.assertEqual(response.json()['optical_element_groups'], self.instrument_capability.optical_element_groups)
        self.assertEqual(response.json()['operation_modes'], self.instrument_capability.operation_modes)
        # Now set a new capability on the instrument
        status = {'instrument': self.instrument.id,
                  'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                 }
        self._create_instrument_capability(status)
        # Now get the instrument and see that this capability is blended in
        response = self.client.get(reverse('api:instrument-detail', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['optical_element_groups'], {})
        self.assertEqual(response.json()['operation_modes'], {})

    def test_create_instrument_capability_in_past(self):
        # Now set a capability on the instrument in the past
        status = {'instrument': self.instrument.id,
                  'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                  'date': (timezone.now() - timedelta(days=1)).isoformat()
                 }
        self._create_instrument_capability(status)

    def test_create_instrument_capability_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        status = {'instrument': self.instrument.id,
                  'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                 }
        response = self.client.post(reverse('api:instrumentcapability-list'), data=status, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_instrument_capability_fails_if_in_future(self):
        status = {'instrument': self.instrument.id,
                  'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                  'date': (timezone.now() + timedelta(days=1)).isoformat()
                 }
        response = self.client.post(reverse('api:instrumentcapability-list'), data=status, format='json')
        self.assertContains(response, 'Date cannot be in the future', status_code=400)

    def test_fails_to_create_instrument_capability_from_instrument_endpoint_bad_status(self):
        # Bad status should fail
        capability = {'status': 'Not a Status',
                  }
        response = self.client.post(reverse('api:instrument-capabilities', args=(self.instrument.id,)), data=capability, format='json')
        self.assertContains(response, 'Not a Status', status_code=400)

    def test_create_instrument_capability_from_instrument_endpoint(self):
        # Set instrument capability without instrument id, that is part of the endpoint instead
        capability = {'status': models.InstrumentCapability.InstrumentStatus.SCHEDULABLE}
        response = self.client.post(reverse('api:instrument-capabilities', args=(self.instrument.id,)), data=capability, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['instrument'], self.instrument.id)
        self.assertEqual(response.json()['status'], capability['status'])
        self.assertEqual(response.json()['optical_element_groups'], {})
        self.assertEqual(response.json()['operation_modes'], {})

    def test_create_instrument_capability_from_instrument_endpoint_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        capability = {'status': models.InstrumentCapability.InstrumentStatus.SCHEDULABLE}
        response = self.client.post(reverse('api:instrument-capabilities', args=(self.instrument.id,)), data=capability, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_getting_all_instrument_capabilities_for_instrument(self):
        self.client.logout()
        # Add a second instrument capability
        second_capablity = mixer.blend(models.InstrumentCapability, instrument=self.instrument, date=timezone.now(),
                                       status=models.InstrumentCapability.InstrumentStatus.SCHEDULABLE
                                      )
        # Test that two telescope statuses are received in latest date order
        response = self.client.get(reverse('api:instrument-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        latest_capability = response.json()[0]
        self.assertEqual(latest_capability['status'], second_capablity.status)
        self.assertEqual(latest_capability['optical_element_groups'], second_capablity.optical_element_groups)
        self.assertEqual(latest_capability['operation_modes'], second_capablity.operation_modes)
        first_capability = response.json()[1]
        self.assertEqual(first_capability['status'], self.instrument_capability.status)
        self.assertEqual(first_capability['optical_element_groups'], self.instrument_capability.optical_element_groups)
        self.assertEqual(first_capability['operation_modes'], self.instrument_capability.operation_modes)


class TestPlannedInstrumentCapability(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User, is_superuser=False)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory, admin=self.user)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.instrument_capability = mixer.blend(models.InstrumentCapability, instrument=self.instrument,
                                                 date=timezone.now(),
                                                 status=models.InstrumentCapability.InstrumentStatus.AVAILABLE,
                                                 optical_element_groups={'filters': {}},
                                                 operation_modes={'readout': {}}
                                                )
        self.planned_instrument_capability = mixer.blend(
            models.PlannedInstrumentCapability, instrument=self.instrument,
            status=models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
            start=timezone.now() + timedelta(days=30),
            end=timezone.now() + timedelta(days=37),
            optical_element_groups={'filters': {}}, operation_modes={'readout': {}}
        )

    def _create_planned_instrument_capability(self, capability):
        response = self.client.post(reverse('api:plannedinstrumentcapability-list'), data=capability, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['instrument'], capability['instrument'])
        self.assertEqual(response.json()['status'], capability['status'])
        self.assertEqual(response.json()['optical_element_groups'], capability.get('optical_element_groups', {}))
        self.assertEqual(response.json()['operation_modes'], capability.get('operation_modes', {}))
        self.assertEqual(response.json()['start'], capability['start'].replace("+00:00", "Z"))
        self.assertEqual(response.json()['end'], capability['end'].replace("+00:00", "Z"))

    def test_create_planned_instrument_capability(self):
        # Now set a new capability on the instrument
        capability = {'instrument': self.instrument.id,
                      'status': models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'start': (timezone.now() + timedelta(days=4)).isoformat(),
                      'end': (timezone.now() + timedelta(days=5)).isoformat()
                     }
        self._create_planned_instrument_capability(capability)
        # Now get the planned capability from the instrument planned capability endpoint
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['status'], capability['status'])
        self.assertEqual(response.json()[0]['operation_modes'], {})
        self.assertEqual(response.json()[0]['optical_element_groups'], {})
        self.assertEqual(response.json()[0]['start'], capability['start'].replace("+00:00", "Z"))
        self.assertEqual(response.json()[0]['end'], capability['end'].replace("+00:00", "Z"))

    def test_create_planned_instrument_capability_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        capability = {'instrument': self.instrument.id,
                      'status': models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'start': (timezone.now() + timedelta(days=4)).isoformat(),
                      'end': (timezone.now() + timedelta(days=5)).isoformat()
                     }
        response = self.client.post(reverse('api:plannedinstrumentcapability-list'), data=capability, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_planned_instrument_capability_from_instrument_endpoint(self):
        # Set planned instrument capability without instrument id, that is part of the endpoint instead
        capability = {'status': models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'start': (timezone.now() + timedelta(days=4)).isoformat(),
                      'end': (timezone.now() + timedelta(days=5)).isoformat()
                     }
        response = self.client.post(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)), data=capability, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['instrument'], self.instrument.id)
        self.assertEqual(response.json()['status'], capability['status'])
        self.assertEqual(response.json()['operation_modes'], {})
        self.assertEqual(response.json()['optical_element_groups'], {})
        self.assertEqual(response.json()['start'], capability['start'].replace("+00:00", "Z"))
        self.assertEqual(response.json()['end'], capability['end'].replace("+00:00", "Z"))

    def test_create_planned_instrument_capability_from_instrument_endpoint_fails_if_not_admin_user(self):
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        capability = {'status': models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'start': (timezone.now() + timedelta(days=4)).isoformat(),
                      'end': (timezone.now() + timedelta(days=5)).isoformat()
                     }
        response = self.client.post(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)), data=capability, format='json')
        self.assertContains(response, 'You do not have permission', status_code=403)

    def test_create_planned_instrument_capability_fails_if_end_before_start(self):
        capability = {'instrument': self.instrument.id,
                      'status': models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'end': (timezone.now() + timedelta(days=4)).isoformat(),
                      'start': (timezone.now() + timedelta(days=5)).isoformat()
                     }
        response = self.client.post(reverse('api:plannedinstrumentcapability-list'), data=capability, format='json')
        self.assertContains(response, 'The end datetime must be greater than or equal to the start datetime', status_code=400)

    def test_getting_all_planned_instrument_capabilities_for_instrument(self):
        self.client.logout()
        # Add a second planned instrument capability
        second_capability = mixer.blend(
            models.PlannedInstrumentCapability, instrument=self.instrument,
            status=models.PlannedInstrumentCapability.InstrumentStatus.UNAVAILABLE,
            start=timezone.now() + timedelta(days=4),
            end=timezone.now() + timedelta(days=5),
        )
        # Test that two planned telescope statuses are received in ascending start date order
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        latest_capability = response.json()[0]
        self.assertEqual(latest_capability['status'], second_capability.status)
        self.assertEqual(latest_capability['start'], second_capability.start.isoformat().replace("+00:00", "Z"))
        first_capability = response.json()[1]
        self.assertEqual(first_capability['status'], self.planned_instrument_capability.status)
        self.assertEqual(first_capability['start'],  self.planned_instrument_capability.start.isoformat().replace("+00:00", "Z"))

    def test_delete_planned_instrument_capability(self):
        capability_id = self.planned_instrument_capability.id
        response = self.client.delete(reverse('api:plannedinstrumentcapability-detail', args=(capability_id,)))
        self.assertEqual(response.status_code, 204)
        # Now check that that planned instrument capability no longer exists
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_delete_planned_instrument_capability_fails_if_not_admin_user(self):
        capability_id = self.planned_instrument_capability.id
        basic_user = mixer.blend(User, is_superuser=False)
        self.client.force_login(basic_user)
        response = self.client.delete(reverse('api:plannedinstrumentcapability-detail', args=(capability_id,)))
        self.assertContains(response, 'You do not have permission', status_code=403)
        # Now check that that planned instrument capability still exists
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_update_planned_instrument_capability_fields(self):
        capability_id = self.planned_instrument_capability.id
        old_start = self.planned_instrument_capability.start
        # Check that that planned instrument capability start time is the old_start
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['start'], old_start.isoformat().replace("+00:00", "Z"))
        # Now patch update to a new start time
        new_start = old_start - timedelta(days=20)
        new_end = new_start + timedelta(days=7)
        update = {
            'start': new_start.isoformat(),
            'end': new_end.isoformat()
        }
        response = self.client.patch(reverse('api:plannedinstrumentcapability-detail', args=(capability_id,)), data=update, format='json')
        self.assertEqual(response.status_code, 200)
        # Now check that that planned instrument capability exists and its start time is the new_start
        response = self.client.get(reverse('api:instrument-planned-capabilities', args=(self.instrument.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['start'], new_start.isoformat().replace("+00:00", "Z"))
        self.assertEqual(response.json()[0]['end'], new_end.isoformat().replace("+00:00", "Z"))
