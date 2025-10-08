#!/usr/bin/env python3
"""
Quick diagnostic script to discover correct column names in problem_list_diagnoses table
"""

from databricks import sql
import os
import json

def execute_query(query: str):
    """Execute Athena query using Databricks SQL"""
    try:
        with sql.connect(
            server_hostname=os.getenv('DATABRICKS_SERVER_HOSTNAME'),
            http_path=os.getenv('DATABRICKS_HTTP_PATH'),
            auth_type='databricks-oauth'
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in results]
                return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# Query schema
query = """
SELECT *
FROM fhir_v2_prd_db.problem_list_diagnoses
LIMIT 1
"""

print("\n" + "="*60)
print("Testing problem_list_diagnoses table schema...")
print("="*60 + "\n")

results = execute_query(query)

if results:
    print(f"✅ Query successful! Found {len(results)} row")
    print(f"\nColumn names in problem_list_diagnoses table:")
    print("-" * 60)
    
    columns = list(results[0].keys())
    for i, col in enumerate(columns, 1):
        print(f"  {i:2}. {col}")
    
    print(f"\n📊 Total columns: {len(columns)}")
    print("\nSample data from first row:")
    print("-" * 60)
    for key, value in results[0].items():
        if value is not None:
            display_value = str(value)[:100]
            print(f"  {key}: {display_value}")
else:
    print("❌ No results returned")

print("\n" + "="*60 + "\n")
