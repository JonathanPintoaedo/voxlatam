# VoxLatam 🎙

Servicio de transcripción, traducción y doblaje con IA para creadores de contenido LATAM.  
Self-hosted · GTX 970 · Python 3.11 · Docker

---

## Stack

| Servicio | Rol |
|----------|-----|
| Whisper Large v3 | Transcripción de audio (GPU) |
| Mistral 7B Q4 via Ollama | Traducción al español |
| Coqui XTTS-v2 | Doblaje de voz con clonación |
| ffmpeg | Extracción y merge de video/audio |
| FastAPI | API REST |
| Celery + Redis | Cola de jobs |
| PostgreSQL | Base de datos |
| Telegram Bot | Canal de clientes |
| React | Panel web |
| Nginx | Reverse proxy + SSL |

---

## Requisitos

- Ubuntu 22.04/24.04
- NVIDIA GPU con CUDA 12.x (GTX 970 ✅)
- Docker + Docker Compose v2
- 16 GB RAM mínimo
- 50 GB de espacio libre (modelos IA)

---

## Setup rápido

```bash
# 1. Clonar/copiar el proyecto
cd ~/PROYECTOS/voxlatam

# 2. Configurar variables de entorno
nano .env
# Completar: DB_PASS, REDIS_PASS, SECRET_KEY, TELEGRAM_BOT_TOKEN, DOMAIN

# 3. Ejecutar setup automático
chmod +x setup.sh
bash setup.sh
```

---

## Configuración manual paso a paso

### 1. Variables de entorno

```bash
# Generar SECRET_KEY
openssl rand -hex 32

# Editar .env con tus valores reales
nano .env
```

### 2. NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-ct.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-ct.gpg] https://#' | \
    sudo tee /etc/apt/sources.list.d/nvidia-ct.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verificar
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### 3. Levantar servicios

```bash
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f worker

# Ver estado
docker compose ps
```

### 4. Descargar modelo Mistral

```bash
docker exec voxlatam-ollama-1 ollama pull mistral:7b-instruct-q4_K_M
```

### 5. SSL con DuckDNS (IP dinámica)

```bash
# Registrar en duckdns.org → crear subdominio
# Instalar certbot
sudo apt install certbot -y

# Obtener certificados
sudo certbot certonly --standalone -d api.TUDOMINIO.duckdns.org
sudo certbot certonly --standalone -d app.TUDOMINIO.duckdns.org

# Copiar al volumen de nginx
sudo cp -rL /etc/letsencrypt/live ~/PROYECTOS/voxlatam/nginx/certs/

# Reemplazar TU_DOMINIO en nginx/conf.d/voxlatam.conf
sed -i 's/TU_DOMINIO/TUDOMINIO.duckdns.org/g' nginx/conf.d/voxlatam.conf

# Reiniciar nginx
docker compose restart nginx
```

---

## Comandos útiles

```bash
# Ver logs del worker de IA
docker compose logs -f worker

# Ver jobs en cola (Redis)
docker exec voxlatam-redis-1 redis-cli -a TU_REDIS_PASS llen celery

# Reiniciar solo el worker
docker compose restart worker

# Detener todo
docker compose down

# Detener y eliminar datos (¡cuidado!)
docker compose down -v
```

---

## Precios configurados

| Servicio | USD/minuto |
|----------|-----------|
| Transcripción | $0.10 |
| Traducción + SRT | $0.18 |
| Video con subtítulos | $0.18 |
| Doblaje completo | $0.50 |

---

## Estructura del proyecto

```
voxlatam/
├── docker-compose.yml
├── .env                    ← configurar antes del setup
├── setup.sh
├── backend/                ← FastAPI
│   ├── main.py
│   ├── core/
│   ├── models/
│   └── routers/
├── worker/                 ← Celery + IA (GPU)
│   ├── tasks.py            ← orquestador
│   ├── transcribe.py       ← Whisper
│   ├── translate.py        ← Mistral
│   ├── tts.py              ← Coqui XTTS-v2
│   ├── video.py            ← ffmpeg
│   └── db.py
├── telegram-bot/           ← Bot de Telegram
│   └── bot.py
├── frontend/               ← React (panel web)
├── nginx/
│   └── conf.d/
├── data/                   ← PostgreSQL + Redis (gitignored)
├── storage/                ← Archivos de jobs (gitignored)
└── models/                 ← Modelos IA (gitignored)
```
