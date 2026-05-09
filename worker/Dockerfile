FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Actualizar pip y setuptools primero
RUN pip install --upgrade pip setuptools wheel

# PyTorch compatible con GTX 970 (Compute Capability 5.2) — CUDA 11.8
RUN pip install --no-cache-dir \
    torch==2.0.1+cu118 \
    torchvision==0.15.2+cu118 \
    torchaudio==2.0.2+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Resto de dependencias
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--concurrency=1", "-Q", "voxlatam"]