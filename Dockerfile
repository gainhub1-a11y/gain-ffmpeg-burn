# ==== Base image ====
FROM python:3.11-slim

# ==== Environment ====
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FFMPEG_BIN=ffmpeg
ENV FONTS_DIR=/usr/share/fonts/truetype

# ==== System deps ====
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-noto \
    fonts-dejavu-core \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ==== Working dir ====
WORKDIR /app

# ==== Copy files ====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ==== Run app ====
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
