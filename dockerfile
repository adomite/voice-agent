FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      libasound2 \
      libsndfile1 \
      portaudio19-dev \
      pulseaudio-utils \
      gcc \
      python3-dev \
      libespeak-ng1 \
      wget \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/models/piper && \
    wget -q -O /app/models/piper/en_US-ryan-high.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx" && \
    wget -q -O /app/models/piper/en_US-ryan-high.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json" && \
    wget -q -O /app/models/piper/es_ES-davefx-medium.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx" && \
    wget -q -O /app/models/piper/es_ES-davefx-medium.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json" && \
    wget -q -O /app/models/piper/pt_BR-faber-medium.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx" && \
    wget -q -O /app/models/piper/pt_BR-faber-medium.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PIPER_MODELS_DIR=/app/models/piper
ENV MEMORY_DIR=/app/memory_data

CMD ["python", "main.py"]