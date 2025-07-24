#!/usr/bin/env python3
"""
Setup script for LIGO, Virgo, and KAGRA observatories in HEROIC
"""
import requests
import json
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000/api"

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def load_token():
    """Load API token from file"""
    token_file = Path('token')
    if not token_file.exists():
        print(f"{Colors.RED}Error: token file not found. Please create a file named 'token' with your API token.{Colors.END}")
        sys.exit(1)
    
    with open(token_file, 'r') as f:
        token = f.read().strip()
    
    print(f"Using token: {token[:10]}...")
    return token

def make_api_call(method, endpoint, data, description, headers, quiet=False):
    """Make API call and return response"""
    if not quiet:
        print(f"\n{Colors.BOLD}>>> {description}{Colors.END}")
    
    url = f"{BASE_URL}/{endpoint}"
    
    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "GET":
            response = requests.get(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if 200 <= response.status_code < 300:
            if not quiet:
                print(f"{Colors.GREEN}✓ Success ({response.status_code}){Colors.END}")
                if response.content:
                    print(json.dumps(response.json(), indent=2))
            return True, response.json() if response.content else {}
        else:
            if not quiet:
                print(f"{Colors.RED}✗ Failed ({response.status_code}){Colors.END}")
                try:
                    print(json.dumps(response.json(), indent=2))
                except:
                    print(response.text)
            return False, None
    
    except requests.exceptions.RequestException as e:
        if not quiet:
            print(f"{Colors.RED}✗ Error: {e}{Colors.END}")
        return False, None

def setup_observatories():
    """Main setup function"""
    # Load token
    token = load_token()
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }
    
    # Track successes
    stats = {
        'observatories': 0,
        'sites': 0,
        'telescopes': 0,
        'instruments': 0,
        'statuses': 0
    }
    
    print(f"\n{Colors.BLUE}{'='*50}")
    print("Setting up gravitational wave observatories...")
    print(f"{'='*50}{Colors.END}")
    
    # LIGO Observatory
    print(f"\n{Colors.BLUE}=== Setting up LIGO ==={Colors.END}")
    
    success, _ = make_api_call("POST", "observatories/", {
        "id": "ligo",
        "name": "Laser Interferometer Gravitational-Wave Observatory"
    }, "Creating LIGO observatory", headers)
    if success: stats['observatories'] += 1
    
    success, _ = make_api_call("POST", "sites/", {
        "id": "ligo.hanford",
        "name": "LIGO Hanford Observatory",
        "observatory": "ligo",
        "timezone": "America/Los_Angeles",
        "latitude": 46.4551,
        "longitude": -119.4075,
        "elevation": 142.0
    }, "Creating LIGO Hanford site", headers)
    if success: stats['sites'] += 1
    
    success, _ = make_api_call("POST", "sites/", {
        "id": "ligo.livingston",
        "name": "LIGO Livingston Observatory",
        "observatory": "ligo",
        "timezone": "America/Chicago",
        "latitude": 30.5629,
        "longitude": -90.7742,
        "elevation": 0.0
    }, "Creating LIGO Livingston site", headers)
    if success: stats['sites'] += 1
    
    success, _ = make_api_call("POST", "telescopes/", {
        "id": "ligo.hanford.h1",
        "name": "LIGO Hanford H1",
        "site": "ligo.hanford",
        "aperture": 4000.0,
        "latitude": 46.4551,
        "longitude": -119.4075,
        "horizon": 0.0,
        "elevation": 142.0
    }, "Creating LIGO Hanford H1 detector", headers)
    if success: stats['telescopes'] += 1
    
    success, _ = make_api_call("POST", "telescopes/", {
        "id": "ligo.livingston.l1",
        "name": "LIGO Livingston L1",
        "site": "ligo.livingston",
        "aperture": 4000.0,
        "latitude": 30.5629,
        "longitude": -90.7742,
        "horizon": 0.0,
        "elevation": 0.0
    }, "Creating LIGO Livingston L1 detector", headers)
    if success: stats['telescopes'] += 1
    
    success, _ = make_api_call("POST", "instruments/", {
        "id": "ligo.hanford.h1.interferometer",
        "name": "H1 GW Interferometer",
        "telescope": "ligo.hanford.h1"
    }, "Creating H1 interferometer instrument", headers)
    if success: stats['instruments'] += 1
    
    success, _ = make_api_call("POST", "instruments/", {
        "id": "ligo.livingston.l1.interferometer",
        "name": "L1 GW Interferometer",
        "telescope": "ligo.livingston.l1"
    }, "Creating L1 interferometer instrument", headers)
    if success: stats['instruments'] += 1
    
    # Virgo Observatory
    print(f"\n{Colors.BLUE}=== Setting up Virgo ==={Colors.END}")
    
    success, _ = make_api_call("POST", "observatories/", {
        "id": "virgo",
        "name": "Virgo Gravitational Wave Observatory"
    }, "Creating Virgo observatory", headers)
    if success: stats['observatories'] += 1
    
    success, _ = make_api_call("POST", "sites/", {
        "id": "virgo.cascina",
        "name": "Virgo Cascina",
        "observatory": "virgo",
        "timezone": "Europe/Rome",
        "latitude": 43.6314,
        "longitude": 10.5045,
        "elevation": 10.0
    }, "Creating Virgo site", headers)
    if success: stats['sites'] += 1
    
    success, _ = make_api_call("POST", "telescopes/", {
        "id": "virgo.cascina.v1",
        "name": "Virgo V1",
        "site": "virgo.cascina",
        "aperture": 3000.0,
        "latitude": 43.6314,
        "longitude": 10.5045,
        "horizon": 0.0,
        "elevation": 10.0
    }, "Creating Virgo V1 detector", headers)
    if success: stats['telescopes'] += 1
    
    success, _ = make_api_call("POST", "instruments/", {
        "id": "virgo.cascina.v1.interferometer",
        "name": "V1 GW Interferometer",
        "telescope": "virgo.cascina.v1"
    }, "Creating V1 interferometer instrument", headers)
    if success: stats['instruments'] += 1
    
    # KAGRA Observatory
    print(f"\n{Colors.BLUE}=== Setting up KAGRA ==={Colors.END}")
    
    success, _ = make_api_call("POST", "observatories/", {
        "id": "kagra",
        "name": "Kamioka Gravitational Wave Detector"
    }, "Creating KAGRA observatory", headers)
    if success: stats['observatories'] += 1
    
    success, _ = make_api_call("POST", "sites/", {
        "id": "kagra.kamioka",
        "name": "KAGRA Kamioka",
        "observatory": "kagra",
        "timezone": "Asia/Tokyo",
        "latitude": 36.4121,
        "longitude": 137.3057,
        "elevation": 414.0
    }, "Creating KAGRA site", headers)
    if success: stats['sites'] += 1
    
    success, _ = make_api_call("POST", "telescopes/", {
        "id": "kagra.kamioka.k1",
        "name": "KAGRA K1",
        "site": "kagra.kamioka",
        "aperture": 3000.0,
        "latitude": 36.4121,
        "longitude": 137.3057,
        "horizon": 0.0,
        "elevation": 414.0
    }, "Creating KAGRA K1 detector", headers)
    if success: stats['telescopes'] += 1
    
    success, _ = make_api_call("POST", "instruments/", {
        "id": "kagra.kamioka.k1.interferometer",
        "name": "K1 GW Interferometer",
        "telescope": "kagra.kamioka.k1"
    }, "Creating K1 interferometer instrument", headers)
    if success: stats['instruments'] += 1
    
    # Add status updates with realistic duty cycles
    print(f"\n{Colors.BLUE}=== Adding status updates (7 days of history) ==={Colors.END}")
    
    # Define detector characteristics and duty cycles
    detectors = {
        "ligo.hanford.h1": {
            "name": "H1",
            "duty_cycle": 0.85,  # 85% uptime
            "sensitivity_range": (160, 180),  # Mpc range when available
        },
        "ligo.livingston.l1": {
            "name": "L1", 
            "duty_cycle": 0.85,  # 85% uptime
            "sensitivity_range": (160, 180),  # Mpc range when available
        },
        "virgo.cascina.v1": {
            "name": "V1",
            "duty_cycle": 0.80,  # 80% uptime
            "sensitivity_range": (50, 70),   # Mpc range when available
        },
        "kagra.kamioka.k1": {
            "name": "K1",
            "duty_cycle": 0.40,  # 40% uptime (commissioning)
            "sensitivity_range": (20, 30),   # Mpc range when available
        }
    }
    
    # Generate status updates for the past 7 days
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)
    
    for detector_id, detector_info in detectors.items():
        print(f"\n  Generating status history for {detector_info['name']}...")
        
        # Generate approximately 100 status changes over 7 days
        # Average time between changes
        avg_hours_between_changes = (7 * 24) / 100
        
        current_time = start_time
        status_count = 0
        
        while current_time < end_time and status_count < 100:
            # Determine if detector is up or down based on duty cycle
            is_available = random.random() < detector_info['duty_cycle']
            
            if is_available:
                status = "AVAILABLE"
                # Random sensitivity within the detector's range
                sensitivity = random.randint(*detector_info['sensitivity_range'])
                reason = "Detector operating normally"
                extra = {"sensitivity": f"{sensitivity} Mpc"}
            else:
                status = "UNAVAILABLE"
                sensitivity = 0
                # Random reasons for downtime
                reasons = [
                    "Scheduled maintenance",
                    "Environmental disturbance",
                    "Technical issue - investigating",
                    "Seismic activity",
                    "Power system maintenance",
                    "Cryogenic system maintenance",
                    "Vacuum system maintenance",
                    "Calibration in progress"
                ]
                reason = random.choice(reasons)
                extra = {"sensitivity": "0 Mpc"}
            
            # Make the API call (quiet mode for status updates)
            success, _ = make_api_call("POST", f"telescopes/{detector_id}/status/", {
                "date": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": status,
                "reason": reason,
                "extra": extra
            }, f"Status update {status_count + 1} for {detector_info['name']}", headers, quiet=True)
            
            if success:
                stats['statuses'] += 1
                status_count += 1
            
            # Move to next time point
            # Add some randomness to the time between changes
            hours_to_add = random.uniform(0.5 * avg_hours_between_changes, 1.5 * avg_hours_between_changes)
            current_time += timedelta(hours=hours_to_add)
        
        print(f"    Added {status_count} status updates for {detector_info['name']}")
    
    # Print summary
    print(f"\n{Colors.BLUE}{'='*50}")
    print(f"{Colors.BOLD}Setup complete!{Colors.END}")
    print(f"{'='*50}{Colors.END}")
    
    print(f"\n{Colors.BOLD}Summary of created resources:{Colors.END}")
    print(f"- Observatories: {stats['observatories']}/3")
    print(f"- Sites: {stats['sites']}/4")
    print(f"- Telescopes/Detectors: {stats['telescopes']}/4")
    print(f"- Instruments: {stats['instruments']}/4")
    print(f"- Status updates: {stats['statuses']} (approximately 100 per detector)")
    
    print(f"\n{Colors.BOLD}You can now query the API to see the data:{Colors.END}")
    print(f"curl -H \"Authorization: Token $(cat token)\" {BASE_URL}/observatories/")
    
    # Optional: Show current state
    print(f"\n{Colors.BOLD}Current observatories:{Colors.END}")
    make_api_call("GET", "observatories/", None, "Fetching observatories", headers)

if __name__ == "__main__":
    setup_observatories()