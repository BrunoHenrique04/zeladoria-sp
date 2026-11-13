# Troubleshooting: falha controlada

A etapa 6 da atividade pede uma falha provocada de propósito, para mostrar que a pipeline bloqueia a entrega e que sabemos achar e corrigir a causa. Este é o roteiro que seguimos.

## Cenário 1: regra de negócio alterada sem ajustar os testes

Alguém decide que 3 apoios já deveriam valer um ponto de prioridade e muda só a constante.

### 1. Reproduzir

Em `app/regras.py`:

```python
APOIOS_POR_PONTO = 3   # era 5
```

```bash
git commit -am "feat: prioridade sobe a cada 3 apoios"
git push
```

### 2. A pipeline bloqueia

O push dispara o Jenkins. O estágio Testes fica vermelho e os estágios seguintes nem começam: nada de imagem nova, nada de deploy. A versão anterior continua no ar, o que dá para conferir em `GET /health` (o campo `versao` não muda).

### 3. Investigar

No log do estágio, o pytest aponta os casos que quebraram:

```
FAILED tests/test_regras.py::test_calcular_pontos[buraco-False-4-3] - assert 4 == 3
FAILED tests/test_api.py::test_apoios_sobem_prioridade - assert 4 == 3
```

Com 4 apoios a ocorrência deveria ter 3 pontos e apareceu com 4. A causa é a constante alterada: a regra documentada no README (1 ponto a cada 5 apoios) deixou de valer, e os testes existem justamente para segurar isso.

### 4. Corrigir

```bash
git revert HEAD
git push
```

### 5. Pipeline verde de novo

O novo push dispara outro build. Os nove estágios passam, a imagem vai para o Docker Hub com uma tag nova e o `GET /health` passa a mostrar essa versão.

## Cenário 2: dependência vulnerável (Trivy)

Para mostrar o bloqueio de segurança, basta trocar uma dependência por uma versão antiga com CVE crítica conhecida no `requirements.txt`, fazer o push e acompanhar: os testes e o Sonar passam, a imagem é construída e o estágio Análise Trivy falha com `exit code 1`, listando a CVE. A imagem não é publicada. A correção é voltar para a versão segura.

O relatório HTML do Trivy de cada build fica em Artefatos, no Jenkins, então dá para comparar o antes e o depois.

## Problemas reais que podem aparecer

| Sintoma | Causa provável | O que fazer |
|---------|----------------|-------------|
| SonarQube reinicia em loop | `vm.max_map_count` baixo | `sudo sysctl -w vm.max_map_count=524288` (o setup já grava isso) |
| `permission denied` no docker.sock dentro do Jenkins | GID do grupo docker diferente | Conferir `DOCKER_GID` no `infra/.env` com `getent group docker` |
| Quality Gate fica esperando até dar timeout | Webhook do Sonar para o Jenkins não existe | Sonar > Administration > Configuration > Webhooks, URL `http://jenkins:8080/sonarqube-webhook/` |
| Push no GitHub não dispara o build | Webhook do GitHub ausente ou porta 8080 fechada | Ver Recent Deliveries no webhook e a regra de entrada da VM |
| Deploy falha com container `unhealthy` | API não conectou no banco | `docker compose -p zeladoria logs api` |
