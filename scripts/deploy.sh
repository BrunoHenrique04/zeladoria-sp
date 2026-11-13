#!/usr/bin/env bash
# Sobe uma nova versão com Docker Compose e guarda qual imagem estava no ar antes,
# para o rollback saber para onde voltar.
# Uso: IMAGE_REF=usuario/zeladoria-sp:tag scripts/deploy.sh
set -euo pipefail

: "${IMAGE_REF:?defina IMAGE_REF, ex: androww/zeladoria-sp:12-a1b2c3d}"
PROJETO="${COMPOSE_PROJECT:-zeladoria}"
ESTADO_DIR="${DEPLOY_STATE_DIR:-.deploy}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$ESTADO_DIR"

anterior=$(docker inspect --format '{{.Config.Image}}' "${PROJETO}-api-1" 2>/dev/null || true)
echo "${anterior}" > "${ESTADO_DIR}/imagem_anterior"
echo "Imagem no ar antes do deploy: ${anterior:-nenhuma}"
echo "Subindo: ${IMAGE_REF}"

if ! IMAGE_REF="$IMAGE_REF" docker compose -p "$PROJETO" -f "${RAIZ}/docker-compose.yml" \
    up -d --wait --wait-timeout 120; then
  echo "O container novo não ficou saudável." >&2
  docker compose -p "$PROJETO" -f "${RAIZ}/docker-compose.yml" logs --tail 50 api >&2 || true
  "${RAIZ}/scripts/rollback.sh"
  exit 1
fi

docker compose -p "$PROJETO" -f "${RAIZ}/docker-compose.yml" ps
