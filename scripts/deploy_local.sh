#!/usr/bin/env bash

set -euo pipefail

TARGET_ENV="${1:-}"

if [[ -z "${TARGET_ENV}" ]]; then
  echo "Usage: $0 <dev|prod>"
  exit 1
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose introuvable"
  exit 1
fi

case "${TARGET_ENV}" in
  dev)
    export COMPOSE_PROJECT_NAME="credit-scoring-dev"
    export POSTGRES_CONTAINER_NAME="credit_scoring_dev_postgres"
    export API_CONTAINER_NAME="credit_scoring_dev_api"
    export STREAMLIT_CONTAINER_NAME="credit_scoring_dev_streamlit"
    export POSTGRES_PORT="5435"
    export API_PORT="8005"
    export STREAMLIT_PORT="8505"
    ;;
  prod|main)
    export COMPOSE_PROJECT_NAME="credit-scoring-prod"
    export POSTGRES_CONTAINER_NAME="credit_scoring_postgres"
    export API_CONTAINER_NAME="credit_scoring_api"
    export STREAMLIT_CONTAINER_NAME="credit_scoring_streamlit"
    export POSTGRES_PORT="5435"
    export API_PORT="8005"
    export STREAMLIT_PORT="8505"
    ;;
  *)
    echo "Environnement inconnu: ${TARGET_ENV}"
    exit 1
    ;;
esac

echo "Deployment environment: ${TARGET_ENV}"
echo "Compose project: ${COMPOSE_PROJECT_NAME}"

"${COMPOSE_CMD[@]}" config >/dev/null
"${COMPOSE_CMD[@]}" up -d --build postgres api streamlit

if [[ -n "${PORTAINER_WEBHOOK_URL:-}" ]]; then
  echo "Calling Portainer webhook"
  curl -fsSL -X POST "${PORTAINER_WEBHOOK_URL}"
fi

echo "Deployment completed"