#!/usr/bin/env bash
set -e

# Change directory to project root
cd "$(dirname "$0")"

echo "========================================================"
echo "  Industrial Edge AI Quality Control & Modbus Gateway"
echo "========================================================"
echo ""

# Install Python requirements
echo "[INFO] Verifying & installing dependencies..."
python3 -m pip install -r requirements.txt

echo ""
echo "[INFO] Launching Industrial QC Gateway & HMI Web Server..."
echo "[INFO] Live SCADA Dashboard: http://localhost:8000"
echo "[INFO] Modbus TCP Server:    localhost:5020"
echo ""

# Launch main application
python3 main.py
