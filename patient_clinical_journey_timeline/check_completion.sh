#!/bin/bash

echo "================================================================================================="
echo "MONITORING TIMELINE EXTRACTION - Date Fix Verification"
echo "================================================================================================="
echo ""

for i in 1 2 3; do
    logfile="output/v43_date_fix_patient${i}.log"
    echo "PATIENT $i:"
    
    if grep -q "FINAL TIMELINE JSON SAVED" "$logfile" 2>/dev/null; then
        echo "  ✅ COMPLETE"
        
        # Check for surgery counts
        surgery_count=$(grep "Added.*surgical procedures" "$logfile" | tail -1 | grep -oE "[0-9]+" | head -1)
        echo "  Surgeries found: $surgery_count"
        
        # Check JSON output exists
        json_file=$(ls -1 output/v43_date_fix_patient${i}/*_timeline.json 2>/dev/null | head -1)
        if [ -n "$json_file" ]; then
            echo "  JSON file: $(basename $json_file)"
        fi
    elif grep -q "ERROR\|FAILED\|Traceback" "$logfile" 2>/dev/null; then
        echo "  ❌ FAILED - Check log for errors"
    else
        # Show current phase
        current_phase=$(tail -20 "$logfile" 2>/dev/null | grep -E "PHASE [0-9]:|Loading " | tail -1)
        if [ -n "$current_phase" ]; then
            echo "  ⏳ IN PROGRESS: $current_phase"
        else
            echo "  ⏳ IN PROGRESS"
        fi
    fi
    echo ""
done

echo "================================================================================================="
