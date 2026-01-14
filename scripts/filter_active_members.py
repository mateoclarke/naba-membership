#!/usr/bin/env python3
"""
Filter NaBA Members CSV to only ACTIVE members.

Reads a CSV (handling common encodings) and writes a new CSV containing only
rows where the 'status' column equals 'active' (case-insensitive).
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import pandas as pd


DEFAULT_INPUT = "NaBA Members.csv"
DEFAULT_OUTPUT = "Jan 2026 NaBA Active Members.csv"


def read_csv_with_fallback_encodings(path: str) -> pd.DataFrame:
    encodings = ["utf-8", "iso-8859-1", "latin-1", "cp1252", "windows-1252"]
    last_err: Optional[Exception] = None

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue

    raise UnicodeDecodeError(
        "utf-8",
        b"",
        0,
        1,
        f"Could not decode '{path}' with any of: {encodings}. Last error: {last_err}",
    )


def filter_active(input_csv: str, output_csv: str) -> int:
    df = read_csv_with_fallback_encodings(input_csv)

    if "status" not in df.columns:
        raise ValueError(
            f"Input CSV missing required column 'status'. Found columns: {list(df.columns)[:20]}..."
        )

    # Keep only active rows (case-insensitive, ignore surrounding whitespace)
    status_norm = df["status"].astype(str).str.strip().str.lower()
    active_df = df[status_norm == "active"].copy()

    # Select only the specified columns
    columns_to_keep = [
        "email",
        "first_name",
        "last_name",
        "status",
        "mepr-address-country",
        "mepr-address-state"
    ]
    
    # Check which columns exist
    existing_columns = [col for col in columns_to_keep if col in active_df.columns]
    missing_columns = [col for col in columns_to_keep if col not in active_df.columns]
    
    if missing_columns:
        print(f"Warning: The following columns were not found in the CSV: {missing_columns}", file=sys.stderr)
    
    if not existing_columns:
        raise ValueError("None of the specified columns were found in the CSV file.")
    
    # Select only the columns that exist
    active_df = active_df[existing_columns].copy()

    # Write output
    active_df.to_csv(output_csv, index=False)

    return len(active_df)


def main() -> None:
    input_csv = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    output_csv = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

    if not os.path.exists(input_csv):
        print(f"Error: input file not found: {input_csv}", file=sys.stderr)
        sys.exit(1)

    try:
        count = filter_active(input_csv, output_csv)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {count} active rows to: {output_csv}")


if __name__ == "__main__":
    main()

