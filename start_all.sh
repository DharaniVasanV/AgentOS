#!/usr/bin/env bash
# start_all.sh
# Unifies the environment for Render: Starts Pulse Audio, applies migrations, 
# spins up Meeting Agent locally, and proxies Email Agent externally.
set -e

echo "Initializing PulseAudio Server..."
rm -rf /tmp/pulse-* /run/pulse /root/.config/pulse/*/native

# Write a proper PulseAudio config to avoid daemon defaulting to error
mkdir -p /root/.config/pulse
cat > /root/.config/pulse/default.pa << 'EOF'
load-module module-null-sink sink_name=meetingsink sink_properties=device.description=meetingsink
load-module module-null-source source_name=silentsrc
set-default-sink meetingsink
set-default-source silentsrc
EOF

pulseaudio --start --exit-idle-time=-1 --disallow-exit --log-target=file:/tmp/pulseaudio.log
sleep 3

# Verify PulseAudio is up
if ! pactl info > /dev/null 2>&1; then
    echo "ERROR: PulseAudio failed to start!" && cat /tmp/pulseaudio.log
    exit 1
fi

# Export so every child process (including Chromium) inherits the correct sink
export PULSE_SINK=meetingsink
export PULSE_SOURCE=silentsrc
echo "PulseAudio ready. Default sink: $(pactl info | grep 'Default Sink')"
echo "PulseAudio ready. Default source: $(pactl info | grep 'Default Source')"


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
