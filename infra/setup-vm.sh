#!/usr/bin/env bash
# Prepara uma VM Ubuntu limpa: Docker, SonarQube (com token, webhook e quality gate)
# e Jenkins já configurado com o job da pipeline.
# Uso: ./infra/setup-vm.sh        (pode rodar de novo sem medo, ele pula o que já fez)
set -euo pipefail

cd "$(dirname "$0")"
ENV_FILE=.env
SONAR=http://localhost:9000

aviso() { echo "AVISO: $*" >&2; }
senha() { openssl rand -hex 16; }
gravar() { # gravar CHAVE VALOR  (substitui ou acrescenta no .env)
  if grep -q "^$1=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"
  else
    echo "$1=$2" >> "$ENV_FILE"
  fi
}

echo "==> 1/5 Pacotes e Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo apt-get install -y -qq jq openssl >/dev/null
sudo usermod -aG docker "$USER"
DOCKER="sudo docker"

# O Elasticsearch embutido no SonarQube exige este limite
echo "vm.max_map_count=524288" | sudo tee /etc/sysctl.d/99-sonarqube.conf >/dev/null
sudo sysctl -q --system

sudo mkdir -p /var/jenkins_home
sudo chown 1000:1000 /var/jenkins_home

echo "==> 2/5 Arquivo .env"
if [[ ! -f "$ENV_FILE" ]]; then
  ip_publico=$(curl -fsS --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')
  read -rp "Usuário do Docker Hub [androww]: " dh_user
  dh_user=${dh_user:-androww}
  read -rsp "Access token do Docker Hub (não aparece na tela): " dh_token; echo
  [[ -n "$dh_token" ]] || { echo "Token vazio, abortando." >&2; exit 1; }

  umask 077
  cat > "$ENV_FILE" <<EOF
GIT_REPO_URL=https://github.com/BrunoHenrique04/zeladoria-sp.git
JENKINS_URL=http://${ip_publico}:8080/
JENKINS_ADMIN_USER=admin
JENKINS_ADMIN_PASSWORD=$(senha)
DOCKER_GID=$(getent group docker | cut -d: -f3)
DOCKERHUB_USER=${dh_user}
DOCKERHUB_TOKEN=${dh_token}
DOCKERHUB_REPO=${dh_user}/zeladoria-sp
SONAR_DB_PASSWORD=$(senha)
SONAR_ADMIN_PASSWORD=Zel-$(senha)
SONAR_TOKEN=
APP_DB_PASSWORD=$(senha)
EOF
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

echo "==> 3/5 SonarQube (demora uns 2 minutos na primeira vez)"
$DOCKER compose -f docker-compose.ci.yml up -d sonar-db sonarqube
until [[ "$(curl -fsS "$SONAR/api/system/status" 2>/dev/null | jq -r .status)" == "UP" ]]; do
  sleep 5; printf .
done; echo " no ar"

echo "==> 4/5 Token, webhook e quality gate do SonarQube"
if [[ -z "${SONAR_TOKEN:-}" ]]; then
  curl -fsS -u admin:admin -X POST "$SONAR/api/users/change_password" \
    -d login=admin -d previousPassword=admin --data-urlencode "password=$SONAR_ADMIN_PASSWORD" \
    || aviso "não troquei a senha do admin (já foi trocada antes?)"
  AUTH="admin:$SONAR_ADMIN_PASSWORD"

  SONAR_TOKEN=$(curl -fsS -u "$AUTH" -X POST "$SONAR/api/user_tokens/generate" \
    -d "name=jenkins-$(date +%s)" -d type=GLOBAL_ANALYSIS_TOKEN | jq -r .token)
  [[ -n "$SONAR_TOKEN" && "$SONAR_TOKEN" != null ]] || { echo "Não consegui gerar o token do Sonar." >&2; exit 1; }
  gravar SONAR_TOKEN "$SONAR_TOKEN"

  # O Sonar avisa o Jenkins quando a análise termina (o waitForQualityGate depende disso)
  curl -fsS -u "$AUTH" -X POST "$SONAR/api/webhooks/create" \
    -d name=jenkins -d url=http://jenkins:8080/sonarqube-webhook/ >/dev/null \
    || aviso "webhook não criado, crie em Administration > Configuration > Webhooks"

  # Quality gate próprio: além das regras de código novo, cobra o projeto inteiro
  GATE="Zeladoria SP"
  if curl -fsS -u "$AUTH" -X POST "$SONAR/api/qualitygates/create" --data-urlencode "name=$GATE" >/dev/null; then
    condicao() {
      curl -fsS -u "$AUTH" -X POST "$SONAR/api/qualitygates/create_condition" \
        --data-urlencode "gateName=$GATE" -d "metric=$1" -d "op=$2" -d "error=$3" >/dev/null \
        || aviso "condição $1 não criada"
    }
    condicao coverage LT 80
    condicao reliability_rating GT 1
    condicao security_rating GT 1
    condicao duplicated_lines_density GT 5
    curl -fsS -u "$AUTH" -X POST "$SONAR/api/qualitygates/set_as_default" \
      --data-urlencode "name=$GATE" >/dev/null || aviso "não defini o gate como padrão"
  else
    aviso "quality gate '$GATE' não criado (já existe?). O projeto usa o gate padrão."
  fi
else
  echo "Token já existe no .env, pulando."
fi

echo "==> 5/5 Jenkins"
$DOCKER compose -f docker-compose.ci.yml up -d --build jenkins
until curl -fsS -o /dev/null "http://localhost:8080/login"; do sleep 5; printf .; done; echo " no ar"

cat <<EOF

Pronto.
  Jenkins:    ${JENKINS_URL}            usuário: ${JENKINS_ADMIN_USER}
  SonarQube:  ${JENKINS_URL/8080/9000}  usuário: admin
  Senhas:     grep PASSWORD $(pwd)/.env

Falta só o webhook no GitHub (Settings > Webhooks > Add webhook):
  Payload URL:  ${JENKINS_URL}github-webhook/
  Content type: application/json
  Evento:       Just the push event
EOF
