import pandas as pd

# Load the CSV – adjust the path if needed
# Try different encodings to handle special characters
try:
    df = pd.read_csv('data/NaBA Members.csv', encoding='utf-8')
except UnicodeDecodeError:
    try:
        df = pd.read_csv('data/NaBA Members.csv', encoding='latin-1')
    except UnicodeDecodeError:
        df = pd.read_csv('data/NaBA Members.csv', encoding='iso-8859-1')

# Step 1: filter rows with status "expired" or "none"
filtered = df[df['status'].isin(['expired', 'none'])]

# Step 2: define what counts as having an address.
# We'll consider a row to have an address if any of the address columns is non‑empty / non‑null.
# Only use columns that actually exist in the dataframe
possible_address_cols = [
    'mepr-address-one',
    'mepr-address-two',
    'mepr-address-city',
    'mepr-address-state',
    'mepr-address-country',
    'mepr-address-zip'
]

# Filter to only include columns that exist in the dataframe
address_cols = [col for col in possible_address_cols if col in filtered.columns]

if not address_cols:
    print("Warning: No address columns found in the data!")
    has_address = pd.Series([False] * len(filtered), index=filtered.index)
else:
    required_addr_fields = ['mepr-address-one', 'mepr-address-city', 'mepr-address-state']
    # Only use required fields that actually exist; if any are missing, mark all as False.
    if all(col in filtered.columns for col in required_addr_fields):
        # Check that all required fields are not null AND not empty strings
        has_address = filtered[required_addr_fields].apply(
            lambda row: all(
                pd.notna(row[col]) and str(row[col]).strip() != "" 
                for col in required_addr_fields
            ), 
            axis=1
        )
    else:
        print("Warning: Missing one or more required address columns for completeness check!")
        has_address = pd.Series([False] * len(filtered), index=filtered.index)

# Step 3: compute the numbers
total_members      = len(filtered)
members_with_addr  = has_address.sum()
percentage         = (members_with_addr / total_members) * 100 if total_members else 0

print(f'Total members with status "expired" or "none": {total_members}')
print(f'Among them, members that have an address: {members_with_addr}')
print(f'Percentage with address: {percentage:.2f}%')