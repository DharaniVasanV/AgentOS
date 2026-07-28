#!/usr/bin/env bash
# start_all.sh
# Unifies the environment for Render: Starts Pulse Audio, applies migrations, 
# spins up Meeting Agent locally, and proxies Email Agent externally.
set -e

echo "Initializing PulseAudio Server..."
rm -rf /tmp/pulse-* /run/pulse /root/.config/pulse/*/native
pulseaudio -D --exit-idle-time=-1 --disallow-exit --log-target=stderr &
sleep 3

# Create a null virtual sink that acts as our capture device
pactl load-module module-null-sink sink_name=meetingsink sink_properties=device.description=meetingsink || true
# Make meetingsink the system default so ALL apps (including Chromium) use it
pactl set-default-sink meetingsink
# Also set the monitor as default source so apps that read audio get it from the sink
pactl set-default-source meetingsink.monitor
export PULSE_SINK=meetingsink
export PULSE_SOURCE=meetingsink.monitor
echo "PulseAudio ready. Default sink: meetingsink"

cd /app/meeting-agent
echo "Applying internal Database Migrations..."
alembic upgrade head || echo "No migrations needed or skipped gracefully"

echo "Booting up Background Meeting Agent..."
# Start the meeting bot server silently locally inside the container
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

cd /app/email-agent
echo "Booting up User Dashboard on Public Port..."
PORT=${PORT:-10000}
# Hook exactly to Render's required PORT standard and start web traffic
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
