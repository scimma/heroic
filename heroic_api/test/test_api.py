from rest_framework.test import APITestCase
from mixer.backend.django import mixer
from django.contrib.auth.models import User
from django.urls import reverse

from heroic_api import models


class TestCreateApi(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)

    def test_create_observatory(self):
        observatory = {'id': 'LCO', 'name': 'Las Cumbres Observatory'}
        response = self.client.post(reverse('api:observatory-list'), data=observatory)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], observatory['name'])
        self.assertEqual(response.json()['id'], observatory['id'])

    def test_create_site(self):
        site = {'id': 'tst', 'name': 'Test Site', 'observatory': self.observatory.id,
                'elevation': 1000.0}
        response = self.client.post(reverse('api:site-list'), data=site)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], site['name'])
        self.assertEqual(response.json()['id'], site['id'])
        self.assertEqual(response.json()['observatory'], self.observatory.id)

    def test_create_telescope(self):
        telescope = {'id': '1m0a', 'name': '1 meter - 001', 'site': self.site.id,
                     'aperture': 1.0, 'latitude':37.7543, 'longitude': -42.23482}
        response = self.client.post(reverse('api:telescope-list'), data=telescope)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], telescope['name'])
        self.assertEqual(response.json()['id'], telescope['id'])
        self.assertEqual(response.json()['site'], self.site.id)
        self.assertNotIn('status', response.json())
        self.assertNotIn('reason', response.json())
        self.assertNotIn('extra', response.json())

    def test_create_telescope_with_status(self):
        telescope = {'id': '1m0a', 'name': '1 meter - 001', 'site': self.site.id,
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

    def test_create_instrument(self):
        instrument = {'id': 'fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id}
        response = self.client.post(reverse('api:instrument-list'), data=instrument)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], instrument['name'])
        self.assertEqual(response.json()['id'], instrument['id'])
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        self.assertNotIn('status', response.json())
        self.assertNotIn('operation_modes', response.json())
        self.assertNotIn('optical_element_groups', response.json())

    def test_create_instrument_with_capabilities(self):
        instrument = {'id': 'fa01', 'name': 'First Instrument - 001', 'telescope': self.telescope.id,
                      'status': models.InstrumentCapability.InstrumentStatus.UNAVAILABLE,
                      'operation_modes': {'readout': {'default': 'full-frame', 'options': [{'id': 'full-frame', 'name': 'Full Frame Readout Mode'}]}}}
        response = self.client.post(reverse('api:instrument-list'), data=instrument, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], instrument['name'])
        self.assertEqual(response.json()['id'], instrument['id'])
        self.assertEqual(response.json()['telescope'], self.telescope.id)
        self.assertEqual(response.json()['status'], instrument['status'])
        self.assertEqual(response.json()['operation_modes'], instrument['operation_modes'])


class TestTelescopeStatus(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.telescope_status = mixer.blend(models.TelescopeStatus, telescope=self.telescope,
                                            reason='Initial', extra={'key': 'test'})

    def _create_telescope_status(self, status):
        response = self.client.post(reverse('api:telescopestatus-list'), data=status, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['telescope'], status['telescope'])
        self.assertEqual(response.json()['status'], status['status'])
        if 'extra' in status:
            self.assertEqual(response.json()['extra'], status['extra'])
        if 'target' in status:
            self.assertEqual(response.json()['target'], status['target'])
        if 'ra' in status:
            self.assertEqual(response.json()['ra'], status['ra'])
        if 'instrument' in status:
            self.assertEqual(response.json()['instrument'], status['instrument'])

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

    def test_telescope_status_with_pointing(self):
        status = {'telescope': self.telescope.id,
                  'status': models.TelescopeStatus.StatusChoices.POINTING,
                  'extra': {'start': '2024-01-11T03:32:22Z', 'end': '2024-01-12T00:00:00Z'},
                  'ra': 32.31232,
                  'dec': -45.23412,
                  'instrument': self.instrument.id
                 }
        self._create_telescope_status(status)
        # Now get the telescope and see that this status is blended in
        response = self.client.get(reverse('api:telescope-detail', args=(self.telescope.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], status['status'])
        self.assertEqual(response.json()['ra'], status['ra'])
        self.assertEqual(response.json()['instrument'], status['instrument'])

    def test_getting_all_telescope_statuses_for_telescope(self):
        # Add a second telescope status
        second_status = mixer.blend(models.TelescopeStatus, telescope=self.telescope,
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


class TestInstrumentCapability(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = mixer.blend(User)
        self.client.force_login(self.user)
        self.observatory = mixer.blend(models.Observatory)
        self.site = mixer.blend(models.Site, observatory=self.observatory)
        self.telescope = mixer.blend(models.Telescope, site=self.site)
        self.instrument = mixer.blend(models.Instrument, telescope=self.telescope)
        self.instrument_capability = mixer.blend(models.InstrumentCapability, instrument=self.instrument,
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

    def test_fails_to_create_instrument_capability_from_instrument_endpoint(self):
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

    def test_getting_all_instrument_capabilities_for_instrument(self):
        # Add a second instrument capability
        second_capablity = mixer.blend(models.InstrumentCapability, instrument=self.instrument,
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
