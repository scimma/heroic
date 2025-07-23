#!/usr/bin/env python3
"""
Reset HEROIC database to initial state (remove all entries)
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'local_settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from heroic_api.models import (
    Observatory, Site, Telescope, Instrument, 
    TelescopeStatus, TelescopePointing, InstrumentCapability
)

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def confirm_reset():
    """Ask for confirmation before resetting"""
    print(f"{Colors.YELLOW}{Colors.BOLD}WARNING: This will delete all data from the HEROIC database!{Colors.END}")
    print(f"{Colors.YELLOW}This includes:{Colors.END}")
    print("- All observatories, sites, telescopes, and instruments")
    print("- All status updates and capabilities")
    print("- All telescope pointings")
    print("")
    
    response = input(f"{Colors.BOLD}Are you sure you want to continue? (yes/no): {Colors.END}").lower().strip()
    return response == 'yes'

def reset_database():
    """Reset all HEROIC models to empty state"""
    
    if not confirm_reset():
        print(f"{Colors.BLUE}Reset cancelled.{Colors.END}")
        return
    
    print(f"\n{Colors.BLUE}Starting database reset...{Colors.END}")
    
    try:
        with transaction.atomic():
            # Delete in reverse dependency order
            models_to_reset = [
                (InstrumentCapability, "instrument capabilities"),
                (TelescopePointing, "telescope pointings"),
                (TelescopeStatus, "telescope statuses"),
                (Instrument, "instruments"),
                (Telescope, "telescopes"),
                (Site, "sites"),
                (Observatory, "observatories"),
            ]
            
            total_deleted = 0
            
            for model, name in models_to_reset:
                count = model.objects.count()
                if count > 0:
                    print(f"  Deleting {count} {name}...", end='')
                    model.objects.all().delete()
                    print(f" {Colors.GREEN}✓{Colors.END}")
                    total_deleted += count
                else:
                    print(f"  No {name} to delete.")
            
            print(f"\n{Colors.GREEN}{Colors.BOLD}Success!{Colors.END}")
            print(f"Deleted {total_deleted} total entries from the database.")
            
            # Show current state
            print(f"\n{Colors.BOLD}Current database state:{Colors.END}")
            print(f"  Observatories: {Observatory.objects.count()}")
            print(f"  Sites: {Site.objects.count()}")
            print(f"  Telescopes: {Telescope.objects.count()}")
            print(f"  Instruments: {Instrument.objects.count()}")
            print(f"  Telescope Statuses: {TelescopeStatus.objects.count()}")
            print(f"  Telescope Pointings: {TelescopePointing.objects.count()}")
            print(f"  Instrument Capabilities: {InstrumentCapability.objects.count()}")
            
            # Note about users
            user_count = User.objects.count()
            if user_count > 0:
                print(f"\n{Colors.BLUE}Note: {user_count} user account(s) were preserved.{Colors.END}")
                print("User accounts and API tokens are not affected by this reset.")
                
                # Show superuser info
                superusers = User.objects.filter(is_superuser=True)
                if superusers.exists():
                    print(f"\n{Colors.BOLD}Superuser accounts:{Colors.END}")
                    for user in superusers:
                        try:
                            token = Token.objects.get(user=user)
                            print(f"  - {user.username} (token: {token.key[:10]}...)")
                        except Token.DoesNotExist:
                            print(f"  - {user.username} (no token)")
    
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}Error during reset:{Colors.END}")
        print(f"{Colors.RED}{str(e)}{Colors.END}")
        sys.exit(1)

def reset_with_options():
    """Main function with command line options"""
    if len(sys.argv) > 1:
        if sys.argv[1] == '--force':
            # Skip confirmation with --force flag
            print(f"{Colors.YELLOW}Force flag detected, skipping confirmation...{Colors.END}")
            global confirm_reset
            confirm_reset = lambda: True
        elif sys.argv[1] == '--help':
            print("Usage: python reset_database.py [--force]")
            print("")
            print("Reset the HEROIC database to initial state (no entries)")
            print("")
            print("Options:")
            print("  --force    Skip confirmation prompt")
            print("  --help     Show this help message")
            return
    
    reset_database()

if __name__ == "__main__":
    reset_with_options()