from math import cos, radians
from datetime import datetime, timedelta
from django.utils import timezone

from heroic_api.models import Telescope, TargetTypes, PlannedInstrumentCapability, PlannedTelescopeStatus, TelescopeStatus, InstrumentCapability, Instrument

from rise_set.astrometry import (
    make_ra_dec_target, make_minor_planet_target,
    make_comet_target, make_major_planet_target, calculate_airmass_at_times
)
from rise_set.angle import Angle
from rise_set.rates import ProperMotion
from rise_set.visibility import Visibility
from rise_set.exceptions import MovingViolation
from time_intervals.intervals import Intervals

HOURS_PER_DEGREES = 15.0


def get_rise_set_intervals_by_telescope_for_target(data: dict) -> dict:
    """Get rise_set intervals by telescope for a target visibility request

    Note: Non-sidereal intervals are calculated on 15 minute samples
    Parameters:
        data: The validated data from the TargetVisibilityQuerySerializer
    Returns:
        rise_set intervals by telescope
    """
    start = data['start']
    end = data['end']
    intervals_by_telescope = {}
    rise_set_target = get_rise_set_target(data)

    for telescope in data['telescopes']:
        intervals_by_telescope[telescope.id] = []
        rise_set_site = get_rise_set_site(telescope)
        visibility = get_rise_set_visibility(rise_set_site, start, end, telescope)
        try:
            target_intervals = visibility.get_observable_intervals(
                rise_set_target,
                airmass=data['max_airmass'],
                moon_distance=Angle(
                    degrees=data['min_lunar_distance']
                ),
                moon_phase=data.get('max_lunar_phase', 1.0)
            )
            # Use the intervals library to coaslesce adjacent intervals for non-sidereal targets since they are sampled
            # Will probably use more things in Intervals later to intersect/union intervals together
            target_intervals = Intervals(target_intervals)
            # Now attempt to filter out current or historical periods of telescope or instrument UNAVAILABILITY
            if data['include_status']:
                unavailable_intervals = get_telescope_unavailable_intervals(start, end, telescope.id)
                target_intervals = target_intervals.subtract(unavailable_intervals)
            # Now attempt to filter out planned future periods of telescope or instrument UNAVAILABILITY
            if data['include_planned_status']:
                unavailable_intervals = get_telescope_future_unavailable_intervals(start, end, telescope.id)
                target_intervals = target_intervals.subtract(unavailable_intervals)
            intervals_by_telescope[telescope.id] = target_intervals.toTupleList()
        except MovingViolation:
            pass
                
    return intervals_by_telescope


def get_telescope_unavailable_intervals(start, end, telescope_id):
    """ Get the set of past intervals where the telescope is unavailable or all its instruments are unavailable
    """
    unavailable_intervals = Intervals()
    if start < timezone.now():
        # First get the set of TelescopeStatus intervals where the status is UNAVAILABLE
        status_intervals = []
        status_queryset = TelescopeStatus.objects.filter(telescope__id=telescope_id)
        statuses = status_queryset.filter(date__gte=start)
        # Must include the status before this start date since that status spans the start date
        status_before_object = status_queryset.filter(date__lt=start).first()
        if (status_before_object):
            statuses = statuses | status_queryset.filter(id=status_before_object.id)
        if statuses.count() > 0:
            last_status = None
            for status in statuses.order_by('date'):
                if status.status == TelescopeStatus.StatusChoices.UNAVAILABLE:
                    last_status = status
                elif last_status:
                    status_intervals.append(
                        (max(last_status.date, start), min(status.date, end))
                    )
                    last_status = None
            if last_status:
                status_intervals.append(
                    (max(last_status.date, start), end)
                )
            unavailable_intervals = Intervals(status_intervals)
        # We must then get the set of Intervals where ALL of the Instruments of a Telescope are UNAVAILABLE
        instruments_at_telescope = Instrument.objects.filter(telescope__id=telescope_id)
        first_instrument_intervalset = None
        instrument_intervalsets = []
        for instrument in instruments_at_telescope:
            capability_intervals = []
            capability_queryset = InstrumentCapability.objects.filter(instrument=instrument)
            capabilities = capability_queryset.filter(date__gte=start)
            capability_before_object = capability_queryset.filter(date__lt=start).first()
            if (capability_before_object):
                capabilities = capabilities | capability_queryset.filter(id=capability_before_object.id)
            if capabilities.count() > 0:
                last_capability = None
                for capability in capabilities.order_by('date'):
                    if capability.status == InstrumentCapability.InstrumentStatus.UNAVAILABLE:
                        last_capability = capability
                    elif last_capability:
                        capability_intervals.append(
                            (max(last_capability.date, start), min(capability.date, end))
                        )
                        last_capability = None
                if last_capability:
                    capability_intervals.append(
                        (max(last_capability.date, start), end)
                    )
                if first_instrument_intervalset is None:
                    first_instrument_intervalset = Intervals(capability_intervals)
                else:
                    instrument_intervalsets.append(Intervals(capability_intervals))
        if first_instrument_intervalset:
            if len(instrument_intervalsets) > 0:
                # The intersection of all instrument unavailability intervals on a telescope yields the intervals where ALL instruments are unavailable
                first_instrument_intervalset = first_instrument_intervalset.intersect(instrument_intervalsets)
            # If we have instrument unavailability intervals, then union those with the telescope unavailability intervals
            unavailable_intervals = unavailable_intervals.union([first_instrument_intervalset])

    return unavailable_intervals


def get_telescope_future_unavailable_intervals(start, end, telescope_id):
    """ Get the set of future intervals where the telescope is unavailable or all its instruments are unavailable
    """
    unavailable_intervals = Intervals()
    capped_start = start
    if capped_start < timezone.now():
        capped_start = timezone.now()
    if end > timezone.now():
        # Get the current TelescopeStatus, since if that is unavailable then that is assumed to be the base state into the future
        current_status = TelescopeStatus.objects.filter(telescope__id=telescope_id).first()
        planned_status = PlannedTelescopeStatus.objects.filter(telescope__id=telescope_id, start__lte=end, end__gte=capped_start, status=PlannedTelescopeStatus.StatusChoices.UNAVAILABLE)
        planned_status_intervals = []
        for status in planned_status:
            if current_status is None or current_status.status != status.status:
                planned_status_intervals.append((max(capped_start, status.start), min(status.end, end)))

        if current_status is None or current_status.status != TelescopeStatus.StatusChoices.UNAVAILABLE:
            # In this case, the unavailable intervals are just the planned bad intervals
            unavailable_intervals = Intervals(planned_status_intervals)
        else:
            # In this case, the unavailable intervals are all intervals other than those in planned good statuses
            unavailable_intervals = Intervals([(capped_start, end)]).subtract(Intervals(planned_status_intervals))

        # We must now get the set of planned Intervals where ALL of the Instruments of a Telescope are UNAVAILABLE
        instruments_at_telescope = Instrument.objects.filter(telescope__id=telescope_id)
        first_instrument_intervalset = None
        instrument_intervalsets = []
        for instrument in instruments_at_telescope:
            capability_intervals = []
            current_capability = InstrumentCapability.objects.filter(instrument=instrument).first()
            capability_queryset = PlannedInstrumentCapability.objects.filter(instrument=instrument)
            capabilities = capability_queryset.filter(end__gte=capped_start, start__lte=end)
            for capability in capabilities:
                if current_capability is None or current_capability.status != capability.status:
                    capability_intervals.append((max(capped_start, capability.start), min(end, capability.end)))

            if current_capability is None or current_capability.status != InstrumentCapability.InstrumentStatus.UNAVAILABLE:
                capability_intervalset = Intervals(capability_intervals)
            else:
                capability_intervalset = Intervals([(capped_start, end)]).subtract(Intervals(capability_intervals))

            if first_instrument_intervalset is None:
                first_instrument_intervalset = capability_intervalset
            else:
                instrument_intervalsets.append(capability_intervalset)
        # Now combine the instrument intervalsets to we only have unavailability if ALL instruments were unavailable
        if first_instrument_intervalset:
            if len(instrument_intervalsets) > 0:
                # The intersection of all instrument unavailability intervals on a telescope yields the intervals where ALL instruments are unavailable
                first_instrument_intervalset = first_instrument_intervalset.intersect(instrument_intervalsets)
            # If we have instrument unavailability intervals, then union those with the telescope unavailability intervals
            unavailable_intervals = unavailable_intervals.union([first_instrument_intervalset])

    return unavailable_intervals


def get_rise_set_site(telescope: Telescope):
    return {
        'latitude': Angle(degrees=telescope.latitude),
        'longitude': Angle(degrees=telescope.longitude),
        'horizon': Angle(degrees=telescope.horizon),
        'ha_limit_neg': Angle(degrees=telescope.negative_ha_limit * HOURS_PER_DEGREES),
        'ha_limit_pos': Angle(degrees=telescope.positive_ha_limit * HOURS_PER_DEGREES)
    }


def get_rise_set_visibility(rise_set_site: dict, start: datetime, end: datetime, telescope: Telescope):
    # Get rise set Visibility class for a site/telescope location and date range
    return Visibility(
        site=rise_set_site,
        start_date=start,
        end_date=end,
        horizon=telescope.horizon,
        ha_limit_neg=telescope.negative_ha_limit,
        ha_limit_pos=telescope.positive_ha_limit,
        zenith_blind_spot=telescope.zenith_blind_spot,
        twilight='nautical'
    )


def get_proper_motion(target_dict: dict):
    # This applies to the conversion of proper motion as specified by dividing out the cos dec term
    # and converting from mas/yr to as/yr
    # The proper motion fields are sometimes not present in HOUR_ANGLE targets
    pm = {'pmra': None, 'pmdec': None}
    if 'proper_motion_ra' in target_dict and target_dict['proper_motion_ra']:
        pm['pmra'] = ProperMotion(
            Angle(
                degrees=(target_dict['proper_motion_ra'] / 1000.0 / cos(radians(target_dict['dec']))) / 3600.0,
                units='arc'
            ),
            time='year'
        )
    if 'proper_motion_dec' in target_dict and target_dict['proper_motion_dec']:
        pm['pmdec'] = ProperMotion(
            Angle(
                degrees=(target_dict['proper_motion_dec'] / 1000.0) / 3600.0,
                units='arc'
            ),
            time='year'
        )
    return pm


def get_rise_set_target(target_dict: dict):
    # The data in the dict should contain target_type which has been filled in with inferred type of the target
    if target_dict['target_type'] == TargetTypes.ICRS.name:
        pm = get_proper_motion(target_dict)
        return make_ra_dec_target(
            ra=Angle(degrees=target_dict['ra']),
            dec=Angle(degrees=target_dict['dec']),
            ra_proper_motion=pm['pmra'],
            dec_proper_motion=pm['pmdec'],
            parallax=target_dict.get('parallax', 0.0),
            rad_vel=0.0,
            epoch=target_dict['epoch']
        )
    elif target_dict['target_type'] == TargetTypes.MPC_MINOR_PLANET.name:
        return make_minor_planet_target(
            target_type=target_dict['target_type'],
            epoch=target_dict['epoch_of_elements'],
            inclination=target_dict['orbital_inclination'],
            long_node=target_dict['longitude_of_ascending_node'],
            arg_perihelion=target_dict['argument_of_perihelion'],
            semi_axis=target_dict['mean_distance'],
            eccentricity=target_dict['eccentricity'],
            mean_anomaly=target_dict['mean_anomaly']
        )
    elif target_dict['target_type'] == TargetTypes.MPC_COMET.name:
        return make_comet_target(
            target_type=target_dict['target_type'],
            epoch=target_dict['epoch_of_elements'],
            epochofperih=target_dict['epoch_of_perihelion'],
            inclination=target_dict['orbital_inclination'],
            long_node=target_dict['longitude_of_ascending_node'],
            arg_perihelion=target_dict['argument_of_perihelion'],
            perihdist=target_dict['perihelion_distance'],
            eccentricity=target_dict['eccentricity'],
        )
    elif target_dict['target_type'] == TargetTypes.JPL_MAJOR_PLANET.name:
        return make_major_planet_target(
            target_type=target_dict['target_type'],
            epochofel=target_dict['epoch_of_elements'],
            inclination=target_dict['orbital_inclination'],
            long_node=target_dict['longitude_of_ascending_node'],
            arg_perihelion=target_dict['argument_of_perihelion'],
            semi_axis=target_dict['mean_distance'],
            eccentricity=target_dict['eccentricity'],
            mean_anomaly=target_dict['mean_anomaly'],
            dailymot=target_dict['daily_motion']
        )
    else:
        raise TypeError('Invalid target type' + target_dict['type'])


def date_range_for_interval(start: datetime, end: datetime, delta_time=timedelta(minutes=10)):
    time = start
    while time < end:
        yield time
        time += delta_time


def get_airmass_by_telescope_for_target(data: dict) -> dict:
    """Get airmass values by telescope for a target visibility request

    Note: Airmasses are calculated on 10 minute samples
    Parameters:
        data: The validated data from the TargetVisibilityQuerySerializer
    Returns:
        airmass_data: dictionary of telescope id to dictionary of lists of times and airmasses for plotting
    """
    airmass_data = {}
    visibility_intervals = get_rise_set_intervals_by_telescope_for_target(data)
    rise_set_target = get_rise_set_target(data)
    for telescope in data['telescopes']:
        if telescope.id in visibility_intervals:
            night_times = []
            # Expand the visibility intervals into a list of datetimes sampled through the intervals
            for interval in visibility_intervals[telescope.id]:
                night_times.extend(
                    [time for time in date_range_for_interval(interval[0].replace(tzinfo=None), interval[1].replace(tzinfo=None))]
                )
            if len(night_times) > 0:
                airmass_data[telescope.id] = {
                    'times': [time.isoformat() for time in night_times]
                }
                # Calculate airmass values at sampled datetimes
                latitude = Angle(degrees=telescope.latitude)
                longitude = Angle(degrees=telescope.longitude)
                altitude = telescope.site.elevation
                airmasses = calculate_airmass_at_times(
                    night_times, rise_set_target, latitude, longitude, altitude
                )
                airmass_data[telescope.id]['airmasses'] = airmasses
    return airmass_data

def telescope_dark_intervals(telescope: Telescope, start: datetime = timezone.now(), end: datetime = (timezone.now() + timedelta(hours=36))) -> list:
    rise_set_site = get_rise_set_site(telescope)
    visibility = get_rise_set_visibility(rise_set_site, start, end, telescope)
    dark_intervals = visibility.get_dark_intervals()
    return dark_intervals
