#!/bin/bash
# ─────────────────────────────────────────────────────
# VoxLatam — Script de setup inicial
# Ejecutar con: bash setup.sh
# ─────────────────────────────────────────────────────

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}    VoxLatam — Setup Inicial                    ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. Verificar .env
if [ ! -f .env ]; then
    echo -e "${RED}❌ Archivo .env no encontrado.${NC}"
    echo "Copia el .env y completa las variables antes de continuar."
    exit 1
fi

# 2. Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Instalando Docker...${NC}"
    curl -fsSL https://get.docker.com | bash
    sudo usermod -aG docker $USER
fi

# 3. Verificar NVIDIA Container Toolkit
if ! docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}Instalando NVIDIA Container Toolkit...${NC}"
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-ct.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-ct.gpg] https://#' | \
        sudo tee /etc/apt/sources.list.d/nvidia-ct.list
    sudo apt update && sudo apt install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    echo -e "${GREEN}✅ NVIDIA Container Toolkit instalado${NC}"
fi

# 4. Crear directorios necesarios
echo -e "${YELLOW}Creando directorios...${NC}"
mkdir -p data/{postgres,redis} storage models/ollama nginx/certs nginx/logs

# 5. Generar SECRET_KEY si no está configurada
if grep -q "genera_con_openssl" .env; then
    SECRET=$(openssl rand -hex 32)
    sed -i "s/genera_con_openssl_rand_hex_32/$SECRET/" .env
    echo -e "${GREEN}✅ SECRET_KEY generada automáticamente${NC}"
fi

# 6. Levantar stack
echo -e "${YELLOW}Levantando servicios Docker...${NC}"
docker compose up -d --build

# 7. Esperar a que Ollama esté listo y descargar modelo
echo -e "${YELLOW}Esperando que Ollama inicie (30s)...${NC}"
sleep 30
echo -e "${YELLOW}Descargando modelo Mistral 7B para traducción...${NC}"
docker exec voxlatam-ollama-1 ollama pull mistral:7b-instruct-q4_K_M

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ VoxLatam está corriendo!${NC}"
echo ""
echo -e "  API:      ${YELLOW}http://localhost:8000/docs${NC}"
echo -e "  Frontend: ${YELLOW}http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Próximo paso: configura el dominio y SSL${NC}"
echo -e "Ver README.md para instrucciones completas."
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
