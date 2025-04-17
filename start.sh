#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Kill any existing processes on port 6633 and 8000
sudo lsof -t -i tcp:6633 | xargs kill -9
sudo lsof -t -i tcp:8000 | xargs kill -9

# Start FastAPI server first
echo "Starting FastAPI server..."
cd server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

# Wait for FastAPI server to start
echo "Waiting for FastAPI server to initialize..."
sleep 5

# Start POX controller
echo "Starting POX controller..."
cd pox
gnome-terminal --tab -- bash -c "./pox.py openflow.discovery router; exec bash"

# Wait for POX controller to start
echo "Waiting for POX controller to initialize..."
sleep 5

echo "All services started. FastAPI server running on port 8000, POX controller on port 6633"

# Keep the script running
wait $FASTAPI_PID 
