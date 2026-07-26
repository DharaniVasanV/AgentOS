#!/usr/bin/env bash
# entrypoint.sh
#
# Purpose: start a headless PulseAudio server and create the virtual
# sink ("meetingsink") that Chromium plays meeting audio into and that
# ffmpeg (in recorder.py) records from via meetingsink.monitor.
# This is infrastructure setup, not application logic — see
# app/services/recorder.py for why this exists.
set -e


# Clean up stale PulseAudio socket/pid files from previous container runs
rm -rf /tmp/pulse-* /run/pulse /root/.config/pulse/*/native

pulseaudio -D --exit-idle-time=-1 --disallow-exit -v --log-target=stderr &
sleep 2

# Create the virtual sink once; ignore error if it already exists (container restart).
pactl load-module module-null-sink sink_name=meetingsink sink_properties=device.description=meetingsink || true
pactl set-default-sink meetingsink

echo "Running database migrations..."
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
