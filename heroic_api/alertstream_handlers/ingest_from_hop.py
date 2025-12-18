from heroic_api.models import TelescopeStatus, Telescope
from hop.io import Metadata
from hop.models import JSONBlob

from astropy.time import Time
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def ignore_message(blob: JSONBlob, metadata: Metadata):
    """ Ignore the message sent here
    """
    return


def topic_to_gw_telescope(topic: str) -> Telescope:
    telescope_id = topic.split('.')[2]
    try:
        match telescope_id:
            case 'K1':
                return Telescope.objects.get(id='kagra.kamioka.k1')
            case 'L1':
                return Telescope.objects.get(id='ligo.livingston.l1')
            case 'V1':
                return Telescope.objects.get(id='virgo.cascina.v1')
            case 'H1':
                return Telescope.objects.get(id='ligo.hanford.h1')
            case _:
                return Telescope.objects.none
    except Telescope.DoesNotExist:
        return Telescope.objects.none


def state_to_telescope_status(state: str) -> str:
    match state:
        case 'Observing' | 'Ready' | 'Injection':
            return TelescopeStatus.StatusChoices.AVAILABLE
        case _:
            return TelescopeStatus.StatusChoices.UNAVAILABLE


def gps_to_datetime(gps_time: float) -> datetime:
    time = Time(gps_time, format='gps', scale='utc')
    return time.datetime.replace(tzinfo=timezone.utc)


def handle_igwn_sensistivity_message(blob: JSONBlob, metadata: Metadata):
    """ Called with sensitivity range_history messages for the LVK telescopes
    """
    telescope = topic_to_gw_telescope(metadata.topic)
    if not telescope:
        logger.error(f"Could not find a telescope associated with topic {metadata.topic}")
        return

    old_telescope = TelescopeStatus.objects.filter(telescope=telescope).first()
    if old_telescope:
        old_status = old_telescope.status
    else:
        old_status = TelescopeStatus.StatusChoices.UNAVAILABLE

    status = TelescopeStatus.objects.create(
        telescope=telescope,
        date=gps_to_datetime(blob.content['time'][0]),
        status=old_status,
        extra={'sensitivity': blob.content['data'][0]}
    )
    logger.info(f"Created state for telescope {telescope.id} with status {status.status} and sensitivity {status.extra['sensitivity']}")


def handle_igwn_status_message(blob: JSONBlob, metadata: Metadata):
    """ Called with status messages for the LVK telescopes
    """
    telescope = topic_to_gw_telescope(metadata.topic)
    if not telescope:
        logger.error(f"Could not find a telescope associated with topic {metadata.topic}")
        return

    status = TelescopeStatus.objects.create(
        telescope=telescope,
        date=gps_to_datetime(blob.content['time']),
        status=state_to_telescope_status(blob.content['state']),
    )
    logger.info(f"Created state for telescope {telescope.id} with status {status.status}")
