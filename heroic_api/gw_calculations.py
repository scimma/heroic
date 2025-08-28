"""
Gravitational Wave specific calculations for HEROIC
Including antenna patterns, SNR calculations, and network sensitivity
"""
import numpy as np
from math import sin, cos, sqrt, pi, atan2
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from pyslalib import slalib
from rise_set.astrometry import gregorian_to_ut_mjd, ut_mjd_to_gmst


def get_detector_arm_directions(detector_id: str) -> Dict[str, Tuple[float, float, float]]:
    """
    Get the detector parameters including arm directions
    
    Returns dict with:
        - latitude, longitude in degrees
        - x_arm_azimuth, y_arm_azimuth in degrees
        - x_arm, y_arm: unit vectors in local frame (North, East, Up)
    """
    # Detector parameters from LAL/literature
    # Arm azimuths are measured clockwise from North
    detector_params = {
        "ligo.hanford.h1": {
            "latitude": 46.4551,
            "longitude": -119.4075,
            "x_arm_azimuth": 125.9994,  # degrees from North
            "y_arm_azimuth": 215.9994,  # degrees from North
            "elevation": 142.554,  # meters
        },
        "ligo.livingston.l1": {
            "latitude": 30.5629,
            "longitude": -90.7742,
            "x_arm_azimuth": 197.7165,
            "y_arm_azimuth": 287.7165,
            "elevation": -6.574,
        },
        "virgo.cascina.v1": {
            "latitude": 43.6314,
            "longitude": 10.5045,
            "x_arm_azimuth": 70.5674,
            "y_arm_azimuth": 160.5674,
            "elevation": 51.884,
        },
        "kagra.kamioka.k1": {
            "latitude": 36.4121,
            "longitude": 137.3057,
            "x_arm_azimuth": 90.0,
            "y_arm_azimuth": 0.0,  # North arm
            "elevation": 414.181,
        }
    }
    
    params = detector_params.get(detector_id, None)
    if params is None:
        return None
        
    # Calculate unit vectors for arms in local frame (North, East, Up)
    # Convert azimuth to radians and compute unit vectors
    x_az_rad = np.radians(params['x_arm_azimuth'])
    y_az_rad = np.radians(params['y_arm_azimuth'])
    
    # Unit vectors: azimuth is measured from North clockwise
    # So North component is cos(az), East component is sin(az)
    params['x_arm'] = (cos(x_az_rad), sin(x_az_rad), 0.0)  # (North, East, Up)
    params['y_arm'] = (cos(y_az_rad), sin(y_az_rad), 0.0)
    
    return params


def calculate_gmst(utc_time: datetime) -> float:
    """
    Calculate Greenwich Mean Sidereal Time (GMST) in radians
    
    Uses rise_set.astrometry functions for consistency with
    other astronomical calculations in HEROIC.
    """
    gmst_angle = ut_mjd_to_gmst(gregorian_to_ut_mjd(utc_time))
    # Convert Angle object to radians
    return gmst_angle.in_radians()


def detector_response_tensor(detector_params: Dict) -> np.ndarray:
    """
    Calculate the detector response tensor in Earth-fixed coordinates
    
    The response tensor D^ab = 0.5 * (x^a x^b - y^a y^b)
    where x and y are the unit vectors along the arms
    """
    # Get arm vectors in local coordinates (North, East, Up)
    x_local = np.array(detector_params['x_arm'])
    y_local = np.array(detector_params['y_arm'])
    
    # Convert from local (North, East, Up) to Earth-fixed (x, y, z) coordinates
    lat = np.radians(detector_params['latitude'])
    lon = np.radians(detector_params['longitude'])
    
    # Rotation matrix from local to Earth-fixed coordinates
    # Local: North, East, Up
    # Earth-fixed: x points to 0° lat/lon, y to 90°E, z to North pole
    rotation = np.array([
        [-sin(lat)*cos(lon), -sin(lon), cos(lat)*cos(lon)],
        [-sin(lat)*sin(lon),  cos(lon), cos(lat)*sin(lon)],
        [ cos(lat),           0,        sin(lat)]
    ])
    
    # Transform arm vectors to Earth-fixed coordinates
    x_earth = rotation @ x_local
    y_earth = rotation @ y_local
    
    # Calculate response tensor: D^ab = 0.5 * (x^a x^b - y^a y^b)
    D = 0.5 * (np.outer(x_earth, x_earth) - np.outer(y_earth, y_earth))
    
    return D


def antenna_pattern(ra: float, dec: float, time: datetime, detector_id: str) -> Tuple[float, float]:
    """
    Calculate the antenna pattern functions F+ and Fx for a given sky position and detector
    
    This implementation follows the LAL conventions for GW antenna patterns.
    
    Args:
        ra: Right ascension in degrees (J2000)
        dec: Declination in degrees (J2000)
        time: UTC time for calculation
        detector_id: Detector identifier
    
    Returns:
        (F_plus, F_cross) antenna pattern values
        
    References:
        - Anderson et al., PRD 63, 042003 (2001)
        - LAL XLALComputeDetAMResponse
    """
    detector_params = get_detector_arm_directions(detector_id)
    if not detector_params:
        return 0.0, 0.0
    
    # Convert to radians
    ra_rad = np.radians(ra)
    dec_rad = np.radians(dec)
    
    # Calculate GMST and hour angle
    gmst = calculate_gmst(time)
    hour_angle = gmst - ra_rad
    
    # Source unit vector in Earth-fixed coordinates
    # n = (cos(dec)cos(ha), -cos(dec)sin(ha), sin(dec))
    # where ha is measured East from the meridian
    n = np.array([
        cos(dec_rad) * cos(hour_angle),
        -cos(dec_rad) * sin(hour_angle),
        sin(dec_rad)
    ])
    
    # Get detector response tensor
    D = detector_response_tensor(detector_params)
    
    # Calculate polarization tensors in the wave frame
    # We need two orthogonal vectors perpendicular to n
    # Choose the "preferred" polarization frame (North-oriented)
    
    # Vector pointing to North pole
    z = np.array([0, 0, 1])
    
    # X-axis of wave frame: perpendicular to both n and z
    # If source is at pole, use a different reference
    if abs(n[2]) > 0.99:  # Near pole
        z = np.array([1, 0, 0])  # Use x-axis instead
    
    # Normalized X-axis of wave frame
    X = np.cross(z, n)
    X = X / np.linalg.norm(X)
    
    # Y-axis of wave frame
    Y = np.cross(n, X)
    
    # Polarization tensors
    # e+ = X⊗X - Y⊗Y
    # ex = X⊗Y + Y⊗X
    eplus = np.outer(X, X) - np.outer(Y, Y)
    ecross = np.outer(X, Y) + np.outer(Y, X)
    
    # Contract with detector tensor
    # F+ = D^ab e+_ab
    # Fx = D^ab ex_ab
    F_plus = np.sum(D * eplus)
    F_cross = np.sum(D * ecross)
    
    return F_plus, F_cross


def calculate_single_detector_snr(distance_mpc: float, sensitivity_mpc: float, 
                                  f_plus: float, f_cross: float) -> float:
    """
    Calculate SNR for a single detector given distance and antenna pattern
    
    Args:
        distance_mpc: Source distance in Mpc
        sensitivity_mpc: Detector BNS range in Mpc (average distance for SNR=8)
        f_plus: F+ antenna pattern response at source location
        f_cross: Fx antenna pattern response at source location
    
    Returns:
        SNR value
        
    Notes:
        The BNS range is the sky-averaged distance at which a binary neutron star
        merger would be detected at SNR=8. For a specific sky location, the actual
        sensitivity depends on the antenna pattern response at that location.
    """
    if distance_mpc <= 0 or sensitivity_mpc <= 0:
        return 0.0
    
    # Antenna pattern factor (assumes unpolarized source)
    antenna_factor = sqrt(f_plus**2 + f_cross**2)
    
    # SNR calculation:
    # - BNS range is defined for sky-averaged antenna factor of ~0.44
    # - For a specific sky location, we scale by actual antenna factor
    # - SNR = 8 is the threshold at the BNS range distance
    snr_at_sensitivity = 8.0
    sky_averaged_antenna_factor = 0.44  # Approximate sky average
    snr = snr_at_sensitivity * (sensitivity_mpc / distance_mpc) * (antenna_factor / sky_averaged_antenna_factor)
    
    return snr


def calculate_network_snr(individual_snrs: List[float]) -> float:
    """
    Calculate network SNR from individual detector SNRs
    
    Args:
        individual_snrs: List of SNR values from each detector
    
    Returns:
        Network SNR (quadrature sum)
    """
    return sqrt(sum(snr**2 for snr in individual_snrs if snr > 0))


def find_horizon_distance(available_detectors: List[Dict], ra: float, dec: float, 
                         time: datetime, target_snr: float = 10.0) -> float:
    """
    Find the maximum distance at which a binary neutron star merger at (ra, dec) 
    would be detectable with network SNR >= target_snr
    
    Args:
        available_detectors: List of dicts with 'id' and 'sensitivity' keys
                           where 'sensitivity' is the BNS range in Mpc
        ra: Right ascension in degrees
        dec: Declination in degrees  
        time: UTC time
        target_snr: Required network SNR (default 10)
    
    Returns:
        Maximum detectable distance in Mpc for a source at the specified sky position
        
    Note:
        This is NOT the horizon distance (which assumes optimal orientation).
        This is the actual detection distance for the specific sky position.
    """
    if not available_detectors:
        return 0.0
    
    # Reference distance for SNR calculation
    reference_distance = 1.0  # Mpc
    
    # Calculate antenna patterns and SNR at reference distance for each detector
    individual_snrs_at_ref = []
    
    for det in available_detectors:
        # Get antenna pattern for this sky position
        f_plus, f_cross = antenna_pattern(ra, dec, time, det['id'])
        
        # Extract sensitivity value
        sensitivity = float(det['sensitivity'].replace(' Mpc', ''))
        
        # Calculate SNR at reference distance
        snr_at_ref = calculate_single_detector_snr(
            reference_distance, 
            sensitivity,
            f_plus,
            f_cross
        )
        
        if snr_at_ref > 0:  # Only include detectors with non-zero response
            individual_snrs_at_ref.append(snr_at_ref)
    
    # Calculate network SNR at reference distance
    network_snr_at_ref = calculate_network_snr(individual_snrs_at_ref)
    
    if network_snr_at_ref == 0:
        return 0.0
    
    # Use proportionality: SNR ∝ 1/distance
    # If SNR_ref = network_snr_at_ref at distance = reference_distance
    # Then SNR_target = network_snr_at_ref * (reference_distance / distance_target)
    # Solving for distance_target:
    # distance_target = reference_distance * (network_snr_at_ref / target_snr)
    
    max_distance = reference_distance * (network_snr_at_ref / target_snr)
    
    return max_distance


def calculate_gw_visibility_timeline(
    telescopes_status: Dict[str, List[Dict]], 
    ra: float, 
    dec: float,
    start_time: datetime,
    end_time: datetime,
    time_resolution_minutes: int = 15
) -> List[Dict]:
    """
    Calculate GW network visibility timeline for a sky position
    
    Args:
        telescopes_status: Dict mapping telescope_id to list of status intervals
        ra: Right ascension in degrees
        dec: Declination in degrees
        start_time: Start of query period
        end_time: End of query period
        time_resolution_minutes: Time step for calculations
    
    Returns:
        List of time-stamped visibility data points
    """
    timeline = []
    current_time = start_time
    
    while current_time <= end_time:
        # Find which detectors are available at this time
        available_detectors = []
        
        for telescope_id, status_list in telescopes_status.items():
            for status in status_list:
                if status['start'] <= current_time < status['end'] and status['status'] == 'AVAILABLE':
                    available_detectors.append({
                        'id': telescope_id,
                        'sensitivity': status['sensitivity']
                    })
                    break
        
        # Calculate horizon distance for this configuration
        horizon_distance = find_horizon_distance(
            available_detectors, 
            ra, 
            dec, 
            current_time,
            target_snr=10.0
        )
        
        # Build timeline entry
        entry = {
            'time': current_time.isoformat(),
            'max_distance_snr10_mpc': round(horizon_distance, 1),
            'active_detectors': [det['id'] for det in available_detectors],
            'network_count': len(available_detectors)
        }
        
        # Add individual detector info if requested
        detector_info = {}
        for det in available_detectors:
            f_plus, f_cross = antenna_pattern(ra, dec, current_time, det['id'])
            detector_info[det['id']] = {
                'sensitivity': det['sensitivity'],
                'f_plus': round(f_plus, 3),
                'f_cross': round(f_cross, 3)
            }
        entry['detector_details'] = detector_info
        
        timeline.append(entry)
        
        # Move to next time step
        current_time += timedelta(minutes=time_resolution_minutes)
    
    return timeline