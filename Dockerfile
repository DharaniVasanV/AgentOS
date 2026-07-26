FROM python:3.11-slim

# Install core meeting-agent system dependencies for Playwright/Chromium/Audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    pulseaudio \
    wget \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install both meeting-agent and email-agent requirements simultaneously
COPY email-agent/requirements.txt email_req.txt
COPY meeting-agent/requirements.txt meet_req.txt
RUN pip install --no-cache-dir -r email_req.txt -r meet_req.txt

# Finish Playwright setup
RUN playwright install chromium

# Copy all application code across both modules
COPY . .

# Set up Execution scripts
RUN chmod +x start_all.sh
ENV PYTHONUNBUFFERED=1

# Render will provide the PORT env var natively for the web traffic
EXPOSE 10000

ENTRYPOINT ["./start_all.sh"]
