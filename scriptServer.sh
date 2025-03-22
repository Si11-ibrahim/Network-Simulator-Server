#!/bin/bash


source server/venv/bin/activate
cd server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

