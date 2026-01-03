#!/bin/bash

# Оновлення системи
apt-get update -y
apt-get upgrade -y

# Встановлення Docker
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io

# Встановлення Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Клонування репозиторію
git clone ${DOCKER_COMPOSE_REPO} /opt/whale-bot
cd /opt/whale-bot

# Створення .env файлу (потрібно заповнити вручну)
cp .env.example .env
echo "Відредагуйте .env файл: nano /opt/whale-bot/.env"

# Запуск додатку
docker-compose up -d --build

# Автозапуск при перезавантаженні
echo "@reboot root cd /opt/whale-bot && docker-compose up -d" >> /etc/crontab
