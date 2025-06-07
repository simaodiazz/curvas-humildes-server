#!/bin/bash

# Install dependencies and check updates
pip install -r requirements.txt

# Run code formatter
python -m pylint app/ > reports/lint.log