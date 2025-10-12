#!/bin/bash
#
# Run all config-driven extraction scripts for the patient specified in patient_config.json
#
# Usage: ./run_all_extractions.sh
#

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "================================================================================"
echo "RUNNING ALL CONFIG-DRIVEN EXTRACTION SCRIPTS"
echo "================================================================================"
echo ""

# Check if patient_config.json exists
CONFIG_FILE="../../patient_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: patient_config.json not found at $CONFIG_FILE"
    echo ""
    echo "Run this first:"
    echo "  cd ../../"
    echo "  python3 scripts/initialize_patient_config.py <patient_fhir_id>"
    exit 1
fi

# Read patient info from config
PATIENT_ID=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['fhir_id'])")
OUTPUT_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['output_dir'])")

echo "Patient FHIR ID: $PATIENT_ID"
echo "Output Directory: ../../$OUTPUT_DIR"
echo ""

# Array of extraction scripts
SCRIPTS=(
    "extract_all_encounters_metadata.py"
    "extract_all_medications_metadata.py"
    "extract_all_procedures_metadata.py"
    "extract_all_imaging_metadata.py"
    "extract_all_measurements_metadata.py"
    "extract_all_diagnoses_metadata.py"
    "extract_radiation_data.py"
    "extract_all_binary_files_metadata.py"
)

# Run each script
TOTAL=${#SCRIPTS[@]}
CURRENT=0

for SCRIPT in "${SCRIPTS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo "--------------------------------------------------------------------------------"
    echo "[$CURRENT/$TOTAL] Running: $SCRIPT"
    echo "--------------------------------------------------------------------------------"
    
    if [ ! -f "$SCRIPT" ]; then
        echo "⚠️  Script not found: $SCRIPT (skipping)"
        echo ""
        continue
    fi
    
    START_TIME=$(date +%s)
    
    if python3 "$SCRIPT" 2>&1 | tail -20; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "✅ Completed in ${DURATION}s"
    else
        echo "❌ Failed"
        exit 1
    fi
    
    echo ""
done

echo "================================================================================"
echo "ALL EXTRACTIONS COMPLETE"
echo "================================================================================"
echo ""
echo "Output files in: ../../$OUTPUT_DIR/"
echo ""
echo "Listing generated files:"
ls -lh "../../$OUTPUT_DIR/" 2>/dev/null || echo "Directory not created yet"
echo ""
