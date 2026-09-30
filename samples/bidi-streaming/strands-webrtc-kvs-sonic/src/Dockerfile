# Build for ARM64 (required by AgentCore Runtime)
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim

# Install system dependencies for aiortc and av
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libasound-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    gcc \
    python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py server.py kvs.py audio_track.py webrtc_io.py ./
COPY tools/ ./tools/

# Non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV CONTAINER_ENV=true
ENV PYTHONUNBUFFERED=1

ARG BEDROCK_KB_ID=""
ENV BEDROCK_KB_ID=$BEDROCK_KB_ID

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping').read()"]

CMD ["opentelemetry-instrument", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
