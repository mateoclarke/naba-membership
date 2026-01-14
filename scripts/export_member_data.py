#!/usr/bin/env python3
"""
Export member data as JSON for Astro consumption.
Reads CSV and exports member counts and statistics as JSON files.
"""

import pandas as pd
import json
import sys
import os
from pathlib import Path


def export_member_data(csv_file, output_dir=None):
    """
    Export member data as JSON files for Astro.
    
    Args:
        csv_file: Path to the CSV file with member data
        output_dir: Directory to write JSON files (defaults to astro-app/public/data)
    """
    # Set default output directory
    if output_dir is None:
        repo_root = Path(__file__).resolve().parents[1]
        output_dir = repo_root / "astro-app" / "public" / "data"
    else:
        output_dir = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read the CSV - try multiple encodings
    print(f"Reading data from {csv_file}...")
    encodings = ['utf-8', 'iso-8859-1', 'latin-1', 'cp1252', 'windows-1252']
    df = None
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_file, encoding=encoding)
            print(f"Successfully read CSV with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading with {encoding}: {e}")
            continue
    
    if df is None:
        raise ValueError(f"Could not read CSV file with any of the attempted encodings: {encodings}")
    
    # Filter for all active members
    all_active = df[df['status'] == 'active'].copy()
    total_active = len(all_active)
    
    # Filter for active US members with state data
    us_active = all_active[
        (all_active['mepr-address-country'] == 'US') & 
        (all_active['mepr-address-state'].notna())
    ].copy()
    
    # Count members by state
    # Normalize state codes - handle variations like "NEW YORK" -> "NY"
    state_normalized = us_active['mepr-address-state'].str.upper().str.strip()
    
    # Map common state name variations to codes
    state_name_to_code_map = {
        'NEW YORK': 'NY', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW HAMPSHIRE': 'NH',
        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD',
        'WEST VIRGINIA': 'WV', 'RHODE ISLAND': 'RI', 'DISTRICT OF COLUMBIA': 'DC'
    }
    
    # Replace full state names with codes
    for full_name, code in state_name_to_code_map.items():
        state_normalized = state_normalized.replace(full_name, code)
    
    state_counts = state_normalized.value_counts()
    member_counts_dict = state_counts.to_dict()
    
    # Count Canada members - check for both "CA" code and "Canada" name
    country_normalized = all_active['mepr-address-country'].str.upper().str.strip()
    canada_active = all_active[
        (country_normalized == 'CA') | 
        (country_normalized == 'CANADA')
    ].copy()
    canada_count = len(canada_active)
    
    # Count other international members (not US, not Canada)
    international_active = all_active[
        (all_active['mepr-address-country'].notna()) &
        (country_normalized != 'US') &
        (country_normalized != 'CA') &
        (country_normalized != 'CANADA')
    ].copy()
    international_count = len(international_active)
    
    print(f"\nActive members by state:")
    for state, count in sorted(member_counts_dict.items()):
        print(f"  {state}: {count}")
    print(f"\nCanada: {canada_count}")
    print(f"International: {international_count}")
    print(f"\nTotal active members: {total_active}")
    
    # Create statistics object
    stats_data = {
        'total': total_active,
        'states': dict(sorted(member_counts_dict.items())),
        'canada': canada_count,
        'international': international_count
    }
    
    # State name to code mapping
    state_name_to_code = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC"
    }
    
    # Write JSON files
    member_counts_file = output_dir / "memberCounts.json"
    stats_file = output_dir / "stats.json"
    state_mapping_file = output_dir / "stateMapping.json"
    
    with open(member_counts_file, 'w', encoding='utf-8') as f:
        json.dump(member_counts_dict, f, indent=2)
    print(f"\n✓ Exported member counts to {member_counts_file}")
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=2)
    print(f"✓ Exported statistics to {stats_file}")
    
    with open(state_mapping_file, 'w', encoding='utf-8') as f:
        json.dump(state_name_to_code, f, indent=2)
    print(f"✓ Exported state mapping to {state_mapping_file}")
    
    return {
        'member_counts': member_counts_dict,
        'stats': stats_data,
        'state_mapping': state_name_to_code
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: export_member_data.py <csv_file> [output_dir]")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    export_member_data(csv_file, output_dir)
