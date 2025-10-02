#!/bin/bash

set -e  # exit on error
set -o pipefail

# ----------- INPUTS -----------------
FILEPATH=$1
PROJECT_ID=$2
API_TOKEN=$3
API_URL=$4

# Optional: set default for export type
EXPORT_TYPE=${5:-detailed}  # 'detailed' or 'patient'
INCLUDE_NULL=${6:-true}     # 'true' or 'false'
SLEEP_SECONDS=${7:-20}      # default to 20 seconds if not specified

# ----------- VALIDATION -------------
if [[ -z "$FILEPATH" || -z "$PROJECT_ID" || -z "$API_TOKEN" || -z "$API_URL" ]]; then
  echo "Usage: ./upload_generate_and_fetch_results.sh <file_path> <project_id> <api_token> <api_url> [export_type] [include_null] [sleep_seconds]"
  echo "Example: ./upload_generate_and_fetch_results.sh example.csv 1 my-token http://localhost:8000 detailed true"
  echo "Note: sleep_seconds defaults to 20 if not specified"
  exit 1
fi

echo "🔄 Uploading file and triggering generation..."
api_session_id=$(python3 scripts/upload_file_via_api.py "$FILEPATH" \
  --project-id "$PROJECT_ID" \
  --api-token "$API_TOKEN" \
  --api-url "$API_URL" \
  --generate-after-upload true | grep "API Session ID:" | awk '{print $4}')

if [[ -z "$api_session_id" ]]; then
  echo "❌ Failed to extract API session ID from upload response."
  exit 1
fi

echo "✅ Upload complete. Source task ID: $api_session_id"
echo "⏳ Sleeping $SLEEP_SECONDS seconds to wait for generation to complete..."
sleep "$SLEEP_SECONDS"

echo "⏳ Triggering export task..."
export_response=$(python3 scripts/fetch_results_via_api.py \
  --project-id "$PROJECT_ID" \
  --token "$API_TOKEN" \
  --url "$API_URL" \
  --api-session-id "$api_session_id" \
  --$EXPORT_TYPE \
  --verbose)

export_task_id=$(echo "$export_response" | grep '"api_session_id"' | awk -F'"' '{print $4}' | head -n 1)
if [[ -z "$export_task_id" ]]; then
  echo "❌ Failed to create export task."
  exit 1
fi

echo "📦 Export task created: $export_task_id"
echo "📥 Proceeding to fetch result file..."

if [[ "$INCLUDE_NULL" == "true" ]]; then
  NULL_FLAG="--include-null"
else
  NULL_FLAG="--exclude-null"
fi

# Final CSV fetch
python3 scripts/fetch_results_via_api.py \
  --project-id "$PROJECT_ID" \
  --token "$API_TOKEN" \
  --url "$API_URL" \
  --api-session-id "$export_task_id" \
  --$EXPORT_TYPE \
  $NULL_FLAG \
  --verbose

echo "✅ Done."