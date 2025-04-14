#!/bin/bash
# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Initialize the app
python -c "from app import create_app; create_app()"

# Start Gunicorn with production settings
gunicorn --bind 0.0.0.0:$PORT \
         --workers 4 \
         --timeout 120 \
         --access-logfile - \
         --error-logfile - \
         app:app