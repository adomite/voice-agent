# Dockerfile
FROM python:3.11-slim

# Install system deps for audio + ffmpeg
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      libasound2 \
      libsndfile1 \
      portaudio19-dev \
      pulseaudio-utils \
      gcc \
      python3-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy & install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Use your .env file for API keys
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]