FROM python:3.12-slim

WORKDIR /app

RUN pip install --upgrade pip

# Install system dependencies for av (FFmpeg) and aiortc
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    pkg-config \
    libopus-dev \
    libvpx-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST="0.0.0.0"
ENV PORT=8080

EXPOSE 8080

CMD ["python", "bot.py", "--host", "0.0.0.0", "--port", "8080"]
