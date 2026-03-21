#!/bin/bash

# Script de déploiement local avec gestion des environnements

ENV=${1:-dev}
COMPOSE_PROJECT_NAME="credit-scoring-${ENV}"

echo "🚀 Déploiement en environnement: $ENV"
echo "📦 Nom du projet Docker Compose: $COMPOSE_PROJECT_NAME"

if [ ! -f ".env.$ENV" ]; then
    echo "❌ Fichier .env.$ENV non trouvé!"
    exit 1
fi

echo "✅ Utilisation du fichier: .env.$ENV"

# Charger les variables d'environnement
export $(cat .env.$ENV | xargs)

# Déployer avec le fichier .env approprié
docker compose --file docker-compose.yml \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --env-file ".env.$ENV" \
    up -d --build

echo "✅ Déploiement complété en environnement: $ENV"
docker compose -p "$COMPOSE_PROJECT_NAME" ps
