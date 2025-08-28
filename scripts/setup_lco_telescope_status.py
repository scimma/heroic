#!/usr/bin/env python3
"""
Setup script for simulating LCO telescope status history in HEROIC
This creates realistic status updates for LCO telescopes over the last 7 days
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
    YELLOW = '\033[93m'
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
            response = requests.get(url, headers=headers, params=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if 200 <= response.status_code < 300:
            if not quiet:
                print(f"{Colors.GREEN}✓ Success ({response.status_code}){Colors.END}")
                if response.content and method == "GET":
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

def get_lco_telescopes(headers):
    """Get all LCO telescopes from the API"""
    print(f"\n{Colors.BLUE}=== Fetching LCO telescopes ==={Colors.END}")
    
    # Get all telescopes
    success, data = make_api_call("GET", "telescopes/", None, "Fetching all telescopes", headers)
    
    if not success or not data:
        print(f"{Colors.RED}Failed to fetch telescopes{Colors.END}")
        return []
    
    # Handle paginated response
    if isinstance(data, dict) and 'results' in data:
        telescopes = data['results']
    else:
        telescopes = data
    
    # Filter for LCO telescopes
    lco_telescopes = []
    for telescope in telescopes:
        if telescope['id'].startswith('lco.'):
            lco_telescopes.append(telescope)
    
    print(f"\n{Colors.GREEN}Found {len(lco_telescopes)} LCO telescopes{Colors.END}")
    
    # Group by site for summary
    sites = {}
    for tel in lco_telescopes:
        site_id = '.'.join(tel['id'].split('.')[:2])  # Extract site ID (e.g., "lco.coj")
        if site_id not in sites:
            sites[site_id] = []
        sites[site_id].append(tel)
    
    print(f"\n{Colors.BOLD}LCO Telescope Summary by Site:{Colors.END}")
    for site, telescopes in sorted(sites.items()):
        print(f"  {site}: {len(telescopes)} telescopes")
        for tel in telescopes[:3]:  # Show first 3 telescopes per site
            print(f"    - {tel['id']}: {tel['name']}")
        if len(telescopes) > 3:
            print(f"    ... and {len(telescopes) - 3} more")
    
    return lco_telescopes

def generate_telescope_status_history(telescope, headers, days=7):
    """Generate realistic status history for a telescope"""
    
    # Define telescope characteristics based on aperture size
    aperture = telescope.get('aperture', 1.0)
    
    if aperture >= 2.0:  # 2m telescopes
        duty_cycle = 0.88  # 88% uptime
        weather_loss = 0.15  # 15% weather downtime
    elif aperture >= 1.0:  # 1m telescopes
        duty_cycle = 0.85  # 85% uptime
        weather_loss = 0.18  # 18% weather downtime
    else:  # 0.4m telescopes
        duty_cycle = 0.82  # 82% uptime
        weather_loss = 0.20  # 20% weather downtime
    
    # Site-specific weather patterns
    site_weather = {
        'lco.coj': {'clear': 0.70, 'partly_cloudy': 0.20, 'cloudy': 0.10},  # Siding Spring
        'lco.cpt': {'clear': 0.75, 'partly_cloudy': 0.15, 'cloudy': 0.10},  # South Africa
        'lco.elp': {'clear': 0.65, 'partly_cloudy': 0.25, 'cloudy': 0.10},  # Texas
        'lco.lsc': {'clear': 0.85, 'partly_cloudy': 0.10, 'cloudy': 0.05},  # Chile
        'lco.ogg': {'clear': 0.60, 'partly_cloudy': 0.25, 'cloudy': 0.15},  # Hawaii
        'lco.tfn': {'clear': 0.80, 'partly_cloudy': 0.15, 'cloudy': 0.05},  # Tenerife
    }
    
    site_id = '.'.join(telescope['id'].split('.')[:2])
    weather_probs = site_weather.get(site_id, {'clear': 0.70, 'partly_cloudy': 0.20, 'cloudy': 0.10})
    
    # Generate status updates
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    
    # Average 50-70 status changes per week per telescope
    num_changes = random.randint(50, 70)
    avg_hours_between_changes = (days * 24) / num_changes
    
    current_time = start_time
    status_count = 0
    
    # Status reasons
    scheduled_maintenance_reasons = [
        "Scheduled maintenance - mirror cleaning",
        "Scheduled maintenance - instrument calibration",
        "Scheduled maintenance - filter wheel service",
        "Scheduled maintenance - camera cooling system",
        "Scheduled maintenance - focus mechanism check",
        "Scheduled maintenance - dome rotation service"
    ]
    
    technical_issue_reasons = [
        "Technical issue - camera readout error",
        "Technical issue - dome shutter malfunction",
        "Technical issue - telescope pointing error",
        "Technical issue - filter wheel stuck",
        "Technical issue - cooling system failure",
        "Technical issue - network connectivity",
        "Technical issue - power supply fault",
        "Technical issue - autoguider malfunction"
    ]
    
    weather_reasons = {
        'cloudy': "Weather - thick cloud cover",
        'partly_cloudy': "Weather - intermittent clouds",
        'humidity': "Weather - high humidity (>90%)",
        'wind': "Weather - high winds (>50 km/h)",
        'rain': "Weather - rain",
        'dust': "Weather - dust storm"
    }
    
    while current_time < end_time and status_count < num_changes:
        # Determine telescope status
        rand = random.random()
        
        # Check time of day (assume local night operations)
        hour = current_time.hour
        is_daytime = 10 <= hour <= 22  # Rough approximation
        
        if is_daytime:
            status = "UNAVAILABLE"
            reason = "Daytime - telescope parked"
            extra = {"weather": "daytime"}
        else:
            # Nighttime operations
            if rand < duty_cycle:
                # Telescope is operational
                weather_rand = random.random()
                weather_sum = 0
                weather_condition = None
                
                for condition, prob in weather_probs.items():
                    weather_sum += prob
                    if weather_rand < weather_sum:
                        weather_condition = condition
                        break
                
                if weather_condition == 'clear':
                    status = "AVAILABLE"
                    reason = "Observing - clear skies"
                    extra = {
                        "weather": "clear",
                        "seeing": f"{random.uniform(0.8, 2.5):.1f} arcsec",
                        "transparency": f"{random.uniform(0.7, 1.0):.1f}"
                    }
                elif weather_condition == 'partly_cloudy':
                    if random.random() < 0.6:  # 60% chance still observing
                        status = "AVAILABLE"
                        reason = "Observing - partly cloudy"
                        extra = {
                            "weather": "partly cloudy",
                            "seeing": f"{random.uniform(1.2, 3.0):.1f} arcsec",
                            "transparency": f"{random.uniform(0.4, 0.7):.1f}"
                        }
                    else:
                        status = "UNAVAILABLE"
                        reason = weather_reasons['partly_cloudy']
                        extra = {"weather": "partly cloudy"}
                else:  # cloudy
                    status = "UNAVAILABLE"
                    reason = weather_reasons['cloudy']
                    extra = {"weather": "cloudy"}
            else:
                # Telescope is down
                down_reason_type = random.choice(['maintenance', 'technical', 'weather_extreme'])
                
                if down_reason_type == 'maintenance':
                    status = "UNAVAILABLE"
                    reason = random.choice(scheduled_maintenance_reasons)
                    extra = {"maintenance_type": "scheduled"}
                elif down_reason_type == 'technical':
                    status = "UNAVAILABLE"
                    reason = random.choice(technical_issue_reasons)
                    extra = {"issue_type": "technical"}
                else:  # weather_extreme
                    extreme_weather = random.choice(['humidity', 'wind', 'rain', 'dust'])
                    status = "UNAVAILABLE"
                    reason = weather_reasons[extreme_weather]
                    extra = {"weather": extreme_weather}
        
        # Add enclosure/dome information
        if telescope['id'].endswith('a'):
            extra['enclosure'] = 'clam_a'
        elif telescope['id'].endswith('b'):
            extra['enclosure'] = 'clam_b'
        elif telescope['id'].endswith('c'):
            extra['enclosure'] = 'aqawan_c'
        
        # Make the API call
        success, _ = make_api_call("POST", f"telescopes/{telescope['id']}/status/", {
            "date": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "reason": reason,
            "extra": extra
        }, f"Status update {status_count + 1} for {telescope['id']}", headers, quiet=True)
        
        if success:
            status_count += 1
        
        # Move to next time point
        hours_to_add = random.uniform(0.5 * avg_hours_between_changes, 1.5 * avg_hours_between_changes)
        current_time += timedelta(hours=hours_to_add)
    
    return status_count

def setup_lco_telescope_status():
    """Main function to set up LCO telescope status history"""
    # Load token
    token = load_token()
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }
    
    print(f"\n{Colors.BLUE}{'='*60}")
    print("Setting up LCO telescope status history...")
    print(f"{'='*60}{Colors.END}")
    
    # Get all LCO telescopes
    telescopes = get_lco_telescopes(headers)
    
    if not telescopes:
        print(f"\n{Colors.YELLOW}No LCO telescopes found. Please run ingest_configdb.py first.{Colors.END}")
        return
    
    # Generate status history for each telescope
    print(f"\n{Colors.BLUE}=== Generating 7 days of status history ==={Colors.END}")
    
    total_status_updates = 0
    telescopes_processed = 0
    
    # Process a subset if there are too many telescopes
    max_telescopes = 20  # Limit to avoid overwhelming the system
    
    if len(telescopes) > max_telescopes:
        print(f"\n{Colors.YELLOW}Found {len(telescopes)} telescopes. Processing first {max_telescopes} to avoid overload.{Colors.END}")
        # Select a diverse set - different sites and apertures
        selected_telescopes = []
        sites_seen = set()
        
        # First, get at least one telescope from each site
        for tel in telescopes:
            site = '.'.join(tel['id'].split('.')[:2])
            if site not in sites_seen and len(selected_telescopes) < max_telescopes:
                selected_telescopes.append(tel)
                sites_seen.add(site)
        
        # Fill remaining slots with other telescopes
        for tel in telescopes:
            if tel not in selected_telescopes and len(selected_telescopes) < max_telescopes:
                selected_telescopes.append(tel)
        
        telescopes = selected_telescopes
    
    for telescope in telescopes:
        print(f"\n  Processing {telescope['id']} ({telescope['name']})...")
        count = generate_telescope_status_history(telescope, headers)
        total_status_updates += count
        telescopes_processed += 1
        print(f"    Added {count} status updates")
    
    # Print summary
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{Colors.BOLD}Status history generation complete!{Colors.END}")
    print(f"{'='*60}{Colors.END}")
    
    print(f"\n{Colors.BOLD}Summary:{Colors.END}")
    print(f"- Telescopes processed: {telescopes_processed}")
    print(f"- Total status updates created: {total_status_updates}")
    print(f"- Average updates per telescope: {total_status_updates/telescopes_processed:.1f}")
    
    print(f"\n{Colors.BOLD}You can now query telescope status:{Colors.END}")
    print(f"curl -H \"Authorization: Token $(cat token)\" {BASE_URL}/telescopes/<telescope_id>/status/")
    
    # Show example of current status
    if telescopes:
        example_telescope = telescopes[0]
        print(f"\n{Colors.BOLD}Example - Current status of {example_telescope['id']}:{Colors.END}")
        make_api_call("GET", f"telescopes/{example_telescope['id']}/status/", 
                     {"limit": 5}, "Recent status updates", headers)

if __name__ == "__main__":
    setup_lco_telescope_status()