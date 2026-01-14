#!/usr/bin/env python3
"""
CSV Cleanup Script
Extracts only specified columns from a CSV file and creates a cleaned version.
"""

import pandas as pd
import sys
import os


def clean_csv(input_file, output_file=None):
    """
    Clean CSV file by extracting only specified columns.
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file (optional, defaults to input_file_cleaned.csv)
    """
    # Define the columns to keep
    columns_to_keep = [
        'ID',
        'status',
        'memberships',
        'mepr-address-city',
        'mepr-address-country',
        'mepr-address-state',
        'mepr-address-zip'
    ]
    
    # Generate output filename if not provided
    if output_file is None:
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}_cleaned.csv"
    
    try:
        # Read the CSV file - try multiple encodings
        print(f"Reading CSV file: {input_file}")
        encodings = ['utf-8', 'iso-8859-1', 'latin-1', 'cp1252', 'windows-1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(input_file, encoding=encoding)
                print(f"Successfully read CSV with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading with {encoding}: {e}")
                continue
        
        if df is None:
            raise ValueError(f"Could not read CSV file with any of the attempted encodings: {encodings}")
        
        # Check which columns exist in the file
        existing_columns = [col for col in columns_to_keep if col in df.columns]
        missing_columns = [col for col in columns_to_keep if col not in df.columns]
        
        if missing_columns:
            print(f"Warning: The following columns were not found in the CSV: {missing_columns}")
        
        if not existing_columns:
            print("Error: None of the specified columns were found in the CSV file.")
            return False
        
        # Select only the columns that exist
        df_cleaned = df[existing_columns].copy()
        
        # Write to new CSV file
        print(f"Writing cleaned CSV to: {output_file}")
        df_cleaned.to_csv(output_file, index=False)
        
        print(f"Success! Cleaned CSV created with {len(df_cleaned)} rows and {len(existing_columns)} columns.")
        print(f"Columns included: {', '.join(existing_columns)}")
        
        return True
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        return False
    except Exception as e:
        print(f"Error processing CSV: {str(e)}")
        return False


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python clean_csv.py <input_file> [output_file]")
        print("\nExample:")
        print("  python clean_csv.py members-1768334501.csv")
        print("  python clean_csv.py members-1768334501.csv cleaned_members.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = clean_csv(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
