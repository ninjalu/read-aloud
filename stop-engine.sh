#!/bin/bash
# Stop the background Kokoro voice server (frees the ~1–2 GB of RAM it holds).
# The app will start a fresh one next time you open it.
pkill -f tts_server.py 2>/dev/null && echo "✓ voice engine stopped" || echo "no voice engine was running"
