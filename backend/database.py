import os
import pandas as pd
import sqlite3
from pathlib import Path

# Configuration
CSV_DIR = "VAST-Challenge-2022"
DB_FILE = "vast_challenge.db"

def read_csv_files_to_db(csv_directory, db_file):
    """Read all CSV files from a directory and store them in a SQLite database."""
    
    # Create database connection
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get all CSV files in the directory
    csv_files = Path(csv_directory).glob("**/*.csv")
    
    for csv_file in csv_files:
        print(f"Processing {csv_file.name}...")
        
        try:
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            # Generate table name from filename (remove .csv extension)
            table_name = csv_file.stem.lower().replace("-", "_")
            
            # Write to SQLite database
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"✓ Loaded {csv_file.name} into table '{table_name}'")
            
        except Exception as e:
            print(f"✗ Error processing {csv_file.name}: {e}")
    
    # Close connection
    conn.close()
    print(f"\nDatabase created: {db_file}")

if __name__ == "__main__":
    read_csv_files_to_db(CSV_DIR, DB_FILE)