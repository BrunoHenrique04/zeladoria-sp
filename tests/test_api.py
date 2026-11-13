from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.models import Ocorrencia


def test_health(client):
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "versao": "teste"}


def test_health_sem_banco(client, monkeypatch):
    def conexao_quebrada():
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr("app.main.engine.connect", conexao_quebrada)
    assert client.get("/health").status_code == 503


def test_catalogos(client):
    categorias = client.get("/categorias").json()
    assert {c["codigo"] for c in categorias} >= {"buraco", "alagamento", "iluminacao"}
    assert "santana-tucuruvi" in client.get("/subprefeituras").json()


def test_abrir_ocorrencia_calcula_prioridade_e_prazo(nova_ocorrencia):
    criada = nova_ocorrencia(categoria="alagamento", proximo_equipamento_sensivel=True)

    assert criada["status"] == "aberta"
    assert criada["pontos"] == 7
    assert criada["prioridade"] == "alta"
    aberta = datetime.fromisoformat(criada["aberta_em"])
    prazo = datetime.fromisoformat(criada["prazo_sla"])
    assert prazo - aberta == timedelta(hours=6)
    assert criada["atrasada"] is False


def test_subprefeitura_aceita_maiusculas(nova_ocorrencia):
    assert nova_ocorrencia(subprefeitura=" Santana-Tucuruvi ")["subprefeitura"] == "santana-tucuruvi"


def test_rejeita_categoria_e_subprefeitura_invalidas(client):
    base = {"endereco": "Rua Teste, 10", "descricao": "Descrição longa o bastante"}
    r1 = client.post("/ocorrencias", json={**base, "categoria": "ovni", "subprefeitura": "se"})
    r2 = client.post("/ocorrencias", json={**base, "categoria": "lixo", "subprefeitura": "gotham"})
    assert r1.status_code == 422
    assert r2.status_code == 422


def test_listar_ordena_por_pontos_e_filtra(client, nova_ocorrencia):
    nova_ocorrencia(categoria="calcada")
    nova_ocorrencia(categoria="alagamento", subprefeitura="se")
    nova_ocorrencia(categoria="lixo", subprefeitura="se")

    todas = client.get("/ocorrencias").json()
    assert [o["categoria"] for o in todas] == ["alagamento", "lixo", "calcada"]

    da_se = client.get("/ocorrencias", params={"subprefeitura": "se"}).json()
    assert len(da_se) == 2
    so_lixo = client.get("/ocorrencias", params={"categoria": "lixo"}).json()
    assert len(so_lixo) == 1
    assert client.get("/ocorrencias", params={"status": "resolvida"}).json() == []
    assert len(client.get("/ocorrencias", params={"limite": 1}).json()) == 1


def test_detalhar_e_404(client, nova_ocorrencia):
    criada = nova_ocorrencia()
    assert client.get(f"/ocorrencias/{criada['id']}").json()["id"] == criada["id"]
    assert client.get("/ocorrencias/9999").status_code == 404


def test_ciclo_completo_de_status(client, nova_ocorrencia):
    oid = nova_ocorrencia()["id"]
    for status in ("em_analise", "em_execucao", "resolvida"):
        resposta = client.patch(f"/ocorrencias/{oid}/status", json={"status": status})
        assert resposta.status_code == 200, resposta.text

    resolvida = client.get(f"/ocorrencias/{oid}").json()
    assert resolvida["resolvida_em"] is not None

    reaberta = client.patch(f"/ocorrencias/{oid}/status", json={"status": "reaberta"}).json()
    assert reaberta["resolvida_em"] is None


def test_transicao_invalida_retorna_409(client, nova_ocorrencia):
    oid = nova_ocorrencia()["id"]
    resposta = client.patch(f"/ocorrencias/{oid}/status", json={"status": "resolvida"})
    assert resposta.status_code == 409
    assert "em_analise" in resposta.json()["detail"]


def test_apoios_sobem_prioridade(client, nova_ocorrencia):
    oid = nova_ocorrencia(categoria="buraco")["id"]
    for _ in range(4):
        corpo = client.post(f"/ocorrencias/{oid}/apoios").json()
    assert corpo["pontos"] == 3

    corpo = client.post(f"/ocorrencias/{oid}/apoios").json()
    assert corpo["apoios"] == 5
    assert corpo["pontos"] == 4
    assert corpo["prioridade"] == "media"


def test_ocorrencia_encerrada_nao_recebe_apoio(client, nova_ocorrencia):
    oid = nova_ocorrencia()["id"]
    client.patch(f"/ocorrencias/{oid}/status", json={"status": "cancelada"})
    assert client.post(f"/ocorrencias/{oid}/apoios").status_code == 409
    assert client.post("/ocorrencias/9999/apoios").status_code == 404


def _forcar_prazo(oid: int, prazo: datetime) -> None:
    with SessionLocal() as db:
        db.get(Ocorrencia, oid).prazo_sla = prazo
        db.commit()


def test_metricas_e_atrasadas(client, nova_ocorrencia):
    assert client.get("/ocorrencias/metricas").json()["resolvidas_no_prazo_pct"] is None

    atrasada = nova_ocorrencia(categoria="lixo")["id"]
    _forcar_prazo(atrasada, datetime.now(UTC) - timedelta(hours=1))

    no_prazo = nova_ocorrencia(categoria="buraco")["id"]
    fora_do_prazo = nova_ocorrencia(categoria="iluminacao")["id"]
    for oid in (no_prazo, fora_do_prazo):
        for status in ("em_analise", "em_execucao"):
            client.patch(f"/ocorrencias/{oid}/status", json={"status": status})
    _forcar_prazo(fora_do_prazo, datetime.now(UTC) - timedelta(minutes=5))
    for oid in (no_prazo, fora_do_prazo):
        client.patch(f"/ocorrencias/{oid}/status", json={"status": "resolvida"})

    lista = client.get("/ocorrencias", params={"somente_atrasadas": True}).json()
    assert [o["id"] for o in lista] == [atrasada]

    m = client.get("/ocorrencias/metricas").json()
    assert m["total"] == 3
    assert m["abertas_atrasadas"] == 1
    assert m["por_status"] == {"aberta": 1, "resolvida": 2}
    assert m["resolvidas_no_prazo_pct"] == 50.0
