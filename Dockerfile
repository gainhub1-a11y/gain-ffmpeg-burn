FROM python:3.11-slim

# FFmpeg + libass + font fallback (Noto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fontconfig fonts-noto-core fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py requirements.txt /app/
RUN pip install -r requirements.txt

ENV FFMPEG_BIN=ffmpeg
# Railway userà $PORT automaticamente
CMD ["bash", "-lc", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
