#!/bin/bash
cd "$(dirname "$0")"
echo "============================================"
echo "  HACKING LAB - Educational Lab"
echo "  http://localhost:5000"
echo "  Admin: admin / admin123"
echo "============================================"
echo "Installing Flask if needed..."
pip3 install Flask --break-system-packages -q 2>/dev/null || pip3 install Flask -q
python3 app.py
