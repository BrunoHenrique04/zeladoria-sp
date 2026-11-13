#!/usr/bin/env bash
# Valida a aplicação depois do deploy, falando com ela por HTTP como um cliente faria.
# Uso: scripts/smoke-test.sh <url-base> [versao-esperada]
set -euo pipefail

URL="${1:?informe a URL base, ex: http://localhost:8000}"
VERSAO_ESPERADA="${2:-}"
TENTATIVAS="${SMOKE_TENTATIVAS:-20}"

falhar() { echo "SMOKE FALHOU: $*" >&2; exit 1; }

echo "Aguardando ${URL}/health ..."
for i in $(seq 1 "$TENTATIVAS"); do
  if saude=$(curl -fsS --max-time 3 "${URL}/health" 2>/dev/null); then
    break
  fi
  [[ "$i" -eq "$TENTATIVAS" ]] && falhar "/health não respondeu depois de ${TENTATIVAS} tentativas"
  sleep 3
done
echo "health: ${saude}"

if [[ -n "$VERSAO_ESPERADA" ]]; then
  versao=$(jq -r '.versao' <<<"$saude")
  [[ "$versao" == "$VERSAO_ESPERADA" ]] || falhar "versão no ar é '${versao}', esperava '${VERSAO_ESPERADA}'"
fi

criada=$(curl -fsS --max-time 5 -X POST "${URL}/ocorrencias" \
  -H 'Content-Type: application/json' \
  -d '{"categoria":"alagamento","subprefeitura":"santana-tucuruvi","endereco":"Rua Voluntários da Pátria, 4300","descricao":"Smoke test do pipeline: rua alagada","proximo_equipamento_sensivel":true}') \
  || falhar "POST /ocorrencias não retornou 2xx"

id=$(jq -r '.id' <<<"$criada")
prioridade=$(jq -r '.prioridade' <<<"$criada")
[[ "$prioridade" == "alta" ]] || falhar "regra de prioridade errada: esperava 'alta', veio '${prioridade}'"

curl -fsS --max-time 5 "${URL}/ocorrencias/${id}" >/dev/null || falhar "GET /ocorrencias/${id} falhou"

curl -fsS --max-time 5 -X PATCH "${URL}/ocorrencias/${id}/status" \
  -H 'Content-Type: application/json' -d '{"status":"cancelada"}' >/dev/null \
  || falhar "não consegui cancelar a ocorrência de teste"

curl -fsS --max-time 5 "${URL}/ocorrencias/metricas" >/dev/null || falhar "GET /ocorrencias/metricas falhou"

echo "Smoke test OK (ocorrência de teste #${id} criada e cancelada)"
