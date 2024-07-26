#!/bin/sh
set -e
python -m venv /venv
. /venv/bin/activate
pip install -e .