#!/usr/bin/env bash

echo "Setting up virtual environment..."
python -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements-dev.txt

echo "Your virtual environment should now be active and ready to use!"
echo "To deactivate run: 'deactivate'"