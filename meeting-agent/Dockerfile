FROM python:3.11-slim

# System deps:
# - ffmpeg: audio recording (recorder.py)
# - pulseaudio: virtual audio sink so Chromium's meeting audio can be captured
# - playwright's own --with-deps below pulls in Chromium's system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    pulseaudio \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install Playwright Chromium dependencies manually (Debian Trixie compatible)
# fonts-ubuntu and fonts-unifont are NOT available in Trixie — excluded intentionally.
# For headless Chromium in Docker, only the runtime libs and fonts-liberation are needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
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
RUN playwright install chromium

COPY . .
RUN chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
