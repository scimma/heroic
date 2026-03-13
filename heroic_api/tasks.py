import dramatiq
import logging
import requests
from datetime import timedelta, timezone, datetime

from django.contrib.gis.geos import Point
from django.conf import settings
from astropy.time import Time

from heroic_api.models import TelescopePointing, Telescope, Instrument

logger = logging.getLogger(__name__)


RUBIN_TELESCOPE_ID='noirlab.cp.rubin'
RUBIN_INSTRUMENT_ID='noirlab.cp.rubin.lsstcam'


@dramatiq.actor()
def poll_rubin_schedule():
    try:
        telescope = Telescope.objects.get(id=RUBIN_TELESCOPE_ID)
    except Telescope.DoesNotExist:
        logger.error(f"Cannot poll Rubin schedule: Rubin telescope {RUBIN_TELESCOPE_ID} is not defined")
    try:
        instrument = Instrument.objects.get(id=RUBIN_INSTRUMENT_ID)
    except Instrument.DoesNotExist:
        logger.error(f"Cannot poll Rubin schedule: Rubin instrument {RUBIN_INSTRUMENT_ID} is not defined")
    
    # Get the schedule from 15 minutes in the past until 25 hours later
    start = datetime.now() - timedelta(minutes=15)
    logger.info(f'Getting the Rubin schedule starting at {start.isoformat()}')
    params = {'time': '25', 'start': start.strftime('%Y-%m-%d %H:%M:%S')}
    response = requests.get(settings.RUBIN_SCHEDULE_URL, params=params)
    response.raise_for_status()

    visits = response.json()
    
    # First go through the response and update existing Telescope Pointings which were planned
    # but have now actually occurred
    future_visits = []
    for visit in visits:
        date = Time(visit['t_min'], format='mjd').to_datetime(timezone=timezone.utc)
        point = Point(visit['s_ra'], visit['s_dec'], srid=4326)
        if visit['execution_status'] == 'Performed':
            # Attempt to create or update existing Telescope Pointing for this now completed observation
            TelescopePointing.objects.update_or_create(
                date=date,
                telescope=telescope,
                instrument=instrument,
                coordinate=point,
                target=visit['target_name'],
                defaults={'planned': False, 'extra': {'exposure_time': visit['t_exptime']}}
            )
        elif date > (datetime.now(timezone.utc) - timedelta(minutes=1)):
            # If this is in the future, i.e. a scheduled / planned visit, then collect them up to bulk add
            future_visits.append(
                TelescopePointing(
                    date=date,
                    instrument=instrument,
                    telescope=telescope,
                    target=visit['target_name'],
                    planned=True,
                    coordinate=point,
                    field=point.buffer(visit['s_fov']/2.0),
                    extra={'exposure_time': visit['t_exptime']}
                )
            )
    # After we've updated any completed pointings in the system, we can delete all planned future pointings for
    # Rubin and then add the new planned future pointings in bulk
    num_deleted = TelescopePointing.objects.filter(telescope=telescope, instrument=instrument, planned=True).delete()
    logger.info(f"Deleted {num_deleted[0]} old future Telescope Pointings from the Rubin previous schedule")

    TelescopePointing.objects.bulk_create(future_visits, batch_size=100)
    logger.info(f"Created {len(future_visits)} new future Telescope Pointings from the Rubin schedule")
