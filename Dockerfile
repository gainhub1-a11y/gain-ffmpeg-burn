# Usa una base leggera ma completa
FROM python:3.11-slim

# Installa ffmpeg con libass e i font base
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    libass9 \
    && rm -rf /var/lib/apt/lists/*

# Crea la cartella di lavoro
WORKDIR /app

# Copia i file del progetto
COPY . .

# Installa dipendenze Python
RUN pip install --no-cache-dir fastapi uvicorn

# Porta il server FastAPI
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
