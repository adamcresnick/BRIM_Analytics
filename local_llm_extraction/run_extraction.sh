#!/bin/bash
#
# Quick Start Script for Local LLM Extraction Pipeline
#
# Usage:
#   ./run_extraction.sh <patient_config.yaml>
#
# Example:
#   ./run_extraction.sh ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "========================================================================"
echo "  Local LLM Extraction Pipeline - Quick Start"
echo "========================================================================"
echo ""

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No config file specified${NC}"
    echo ""
    echo "Usage: $0 <patient_config.yaml>"
    echo ""
    echo "Example:"
    echo "  $0 ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml"
    echo ""
    exit 1
fi

CONFIG_FILE="$1"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Config file found: $CONFIG_FILE"

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo -e "${RED}Error: ANTHROPIC_API_KEY environment variable not set${NC}"
    echo ""
    echo "Please set your Anthropic API key:"
    echo "  export ANTHROPIC_API_KEY='your-api-key-here'"
    echo ""
    echo "Get an API key at: https://console.anthropic.com/"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} ANTHROPIC_API_KEY is set"

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."

if ! python3 -c "import anthropic" 2>/dev/null; then
    echo -e "${YELLOW}Warning: anthropic package not found${NC}"
    echo "Installing anthropic..."
    pip3 install anthropic
fi

if ! python3 -c "import pandas" 2>/dev/null; then
    echo -e "${YELLOW}Warning: pandas package not found${NC}"
    echo "Installing pandas..."
    pip3 install pandas
fi

if ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${YELLOW}Warning: pyyaml package not found${NC}"
    echo "Installing pyyaml..."
    pip3 install pyyaml
fi

echo -e "${GREEN}✓${NC} All dependencies installed"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run pipeline
echo ""
echo "========================================================================"
echo "  Starting Extraction Pipeline"
echo "========================================================================"
echo ""

python3 "$SCRIPT_DIR/local_llm_extraction_pipeline.py" "$CONFIG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo -e "  ${GREEN}✓ Pipeline Completed Successfully${NC}"
    echo "========================================================================"
    echo ""
else
    echo ""
    echo "========================================================================"
    echo -e "  ${RED}✗ Pipeline Failed (Exit Code: $EXIT_CODE)${NC}"
    echo "========================================================================"
    echo ""
    exit $EXIT_CODE
fi
