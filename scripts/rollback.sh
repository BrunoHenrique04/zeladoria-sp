#!/usr/bin/env bash
# Volta a aplicação para a imagem que estava no ar antes do último deploy.
set -euo pipefail

PROJETO="${COMPOSE_PROJECT:-zeladoria}"
ESTADO_DIR="${DEPLOY_STATE_DIR:-.deploy}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

anterior=$(cat "${ESTADO_DIR}/imagem_anterior" 2>/dev/null || true)
if [[ -z "$anterior" ]]; then
  echo "Primeiro deploy: não existe versão anterior para voltar." >&2
  exit 1
fi

echo "ROLLBACK: voltando para ${anterior}"
IMAGE_REF="$anterior" docker compose -p "$PROJETO" -f "${RAIZ}/docker-compose.yml" \
  up -d --wait --wait-timeout 120
echo "Rollback concluído. No ar: ${anterior}"
