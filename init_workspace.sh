#!/usr/bin/env bash

echo "Setting up virtual environment..."

virtualenv -p python .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

echo "Your virtual environment should now be active!"
echo "To deactivate run: `deactivate`"