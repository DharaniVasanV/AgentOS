#!/usr/bin/env bash
# start_all.sh
# Unifies the environment for Render: Starts Pulse Audio, applies migrations, 
# spins up Meeting Agent locally, and proxies Email Agent externally.
set -e

echo "Initializing PulseAudio Server..."
rm -rf /tmp/pulse-* /run/pulse /root/.config/pulse

# Start PulseAudio with all warnings silenced. The D-Bus "Unable to contact" message is
# irrelevant in a headless Docker environment - suppress it so set -e is never triggered.
# We use -D (daemonize) and discard stderr (the source of all D-Bus noise).
pulseaudio -D --exit-idle-time=-1 --disallow-exit 2>/dev/null || true
sleep 3

# Load the virtual null sink (our capture target for ffmpeg)
pactl load-module module-null-sink \
    sink_name=meetingsink \
    sink_properties=device.description=meetingsink 2>/dev/null || true

# Set meetingsink as the default audio output for ALL processes (including Chromium)
pactl set-default-sink meetingsink 2>/dev/null || true

# Set meetingsink.monitor as default audio input (virtual mic backed by silence)
pactl set-default-source meetingsink.monitor 2>/dev/null || true

# Confirm it worked
echo "PulseAudio status:"
pactl info 2>/dev/null | grep -E "Default Sink|Default Source" || echo "  (pactl info failed, continuing anyway)"

# Export for child processes (Chromium inherits these)
export PULSE_SINK=meetingsink
export PULSE_SOURCE=meetingsink.monitor


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
