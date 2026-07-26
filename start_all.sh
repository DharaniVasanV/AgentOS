#!/usr/bin/env bash
# start_all.sh
# Unifies the environment for Render: Starts Pulse Audio, applies migrations, 
# spins up Meeting Agent locally, and proxies Email Agent externally.
set -e

echo "Initializing PulseAudio Server..."
rm -rf /tmp/pulse-* /run/pulse /root/.config/pulse/*/native
pulseaudio -D --system --exit-idle-time=-1 --disallow-exit -v --log-target=stderr &
sleep 2

pactl load-module module-null-sink sink_name=meetingsink sink_properties=device.description=meetingsink || true
pactl set-default-sink meetingsink

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
