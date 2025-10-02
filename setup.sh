#!/bin/bash
# Quick setup script for BRIM Analytics pilot

echo "=========================================="
echo "BRIM Analytics - Quick Setup"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Ensure AWS SSO is logged in:"
echo "     aws sso login --profile 343218191717_AWSAdministratorAccess"
echo ""
echo "  2. Run exploration to find patients:"
echo "     python pilot_workflow.py --explore-only"
echo ""
echo "  3. Run pilot extraction:"
echo "     python pilot_workflow.py --patient-id 'Patient/12345' --research-id TEST001"
echo ""
echo "To activate environment manually:"
echo "  source venv/bin/activate"
echo ""
