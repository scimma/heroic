from math import cos, radians
from datetime import datetime, timedelta

from heroic_api.models import Telescope, TargetTypes

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
        target_intervals = Intervals()
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
            intervals_by_telescope[telescope.id] = Intervals(target_intervals).toTupleList()
        except MovingViolation:
            pass
                
    return intervals_by_telescope


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
