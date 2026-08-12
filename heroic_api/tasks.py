import dramatiq
import logging
import requests
import threading
from datetime import timedelta, timezone, datetime

from django.contrib.gis.geos import Point
from django.conf import settings
from astropy.time import Time
from influxdb import InfluxDBClient

from heroic_api.models import TelescopePointing, Telescope, Instrument

logger = logging.getLogger(__name__)


RUBIN_TELESCOPE_ID='noirlab.cp.rubin'
RUBIN_INSTRUMENT_ID='noirlab.cp.rubin.lsstcam'

# Timeouts for the rubin schedule service. It fails and hangs alot
RUBIN_REQUEST_TIMEOUT = (30, 120)

# InfluxDB clients are lazy loaded and cached per worker thread.
_influxdb_thread_local = threading.local()


def get_influxdb_client():
    """Return this thread's cached InfluxDB v1 client, or None if it cannot/should not be built."""
    # 'built' distinguishes "not yet attempted" from "attempted and failed / not configured",
    # so a missing config or construction error is not retried on every single write.
    if getattr(_influxdb_thread_local, 'built', False):
        return _influxdb_thread_local.client

    _influxdb_thread_local.built = True
    _influxdb_thread_local.client = None

    # The connection uses mTLS: the client cert/key authenticate us to the InfluxDB gateway.
    # The gateway serves a publicly-trusted (AWS ACM) cert, so the server is verified against
    # the system CA bundle (verify_ssl=True below).
    cert_path = settings.INFLUXDB_CLIENT_CERT
    key_path = settings.INFLUXDB_CLIENT_KEY
    if not (cert_path and key_path):
        logger.warning(
            'InfluxDB mTLS client cert/key not configured '
            '(INFLUXDB_CLIENT_CERT / INFLUXDB_CLIENT_KEY); request metrics will not be logged.'
        )
        return None

    try:
        _influxdb_thread_local.client = InfluxDBClient(
            host=settings.INFLUXDB_HOST,
            port=settings.INFLUXDB_PORT,
            username=settings.INFLUXDB_USERNAME or None,
            password=settings.INFLUXDB_PASSWORD or None,
            database=settings.INFLUXDB_DATABASE,
            ssl=True,
            verify_ssl=True,
            cert=(cert_path, key_path),
            timeout=settings.INFLUXDB_TIMEOUT,
        )
    except Exception:
        logger.exception('Failed to construct InfluxDB client; request metrics will not be logged.')

    return _influxdb_thread_local.client


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=30000, time_limit=60000)
def write_request_metric(point):
    """Write a single request-metric point (built by the InfluxDBRequestLogger middleware)
    to InfluxDB. Runs on the dramatiq worker so the write stays out of the request path."""
    client = get_influxdb_client()
    if client is None:
        return
    client.write_points([point])


@dramatiq.actor(max_retries=5, min_backoff=5000, max_backoff=300000, time_limit=360000)
def poll_rubin_schedule():
    try:
        telescope = Telescope.objects.get(id=RUBIN_TELESCOPE_ID)
    except Telescope.DoesNotExist:
        logger.error(f"Cannot poll Rubin schedule: Rubin telescope {RUBIN_TELESCOPE_ID} is not defined")
        return
    try:
        instrument = Instrument.objects.get(id=RUBIN_INSTRUMENT_ID)
    except Instrument.DoesNotExist:
        logger.error(f"Cannot poll Rubin schedule: Rubin instrument {RUBIN_INSTRUMENT_ID} is not defined")
        return
    
    # Get the schedule from 15 minutes in the past until 25 hours later
    start = datetime.now() - timedelta(minutes=15)
    logger.info(f'Getting the Rubin schedule starting at {start.strftime("%Y-%m-%d %H:%M:%S")}')
    params = {
        'time': '25',
        'start': start.strftime('%Y-%m-%d %H:%M:%S'),
        'RESPONSEFORMAT': 'json',
        'columns': 't_planning,target_name,s_ra,s_dec,s_fov,t_min,t_exptime,execution_status'
    }
    response = requests.get(settings.RUBIN_SCHEDULE_URL, params=params, timeout=RUBIN_REQUEST_TIMEOUT)
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
                defaults={'planned': False, 'field': point.buffer(visit['s_fov']/2.0), 'extra': {'exposure_time': visit['t_exptime']}}
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
