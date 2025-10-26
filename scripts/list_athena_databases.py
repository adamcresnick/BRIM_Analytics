#!/usr/bin/env python3
"""
List available Athena databases

Usage:
    python3 list_athena_databases.py
"""

import boto3
import sys

AWS_PROFILE = 'radiant-prod'
AWS_REGION = 'us-east-1'

try:
    print("Initializing AWS session...")
    session = boto3.Session(
        profile_name=AWS_PROFILE,
        region_name=AWS_REGION
    )
    athena_client = session.client('athena')
    
    print("\nAvailable Athena databases:")
    print("="*80)
    
    # List catalogs first
    catalogs_response = athena_client.list_data_catalogs()
    
    for catalog in catalogs_response.get('DataCatalogsSummary', []):
        catalog_name = catalog['CatalogName']
        print(f"\nCatalog: {catalog_name}")
        
        try:
            # List databases in this catalog
            db_response = athena_client.list_databases(CatalogName=catalog_name)
            
            for db in db_response.get('DatabaseList', []):
                db_name = db['Name']
                print(f"  - {db_name}")
        except Exception as e:
            print(f"  Error listing databases: {str(e)}")
    
    print("\n" + "="*80)
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
