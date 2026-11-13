import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("APP_VERSION", "teste")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def nova_ocorrencia(client):
    def _criar(**campos):
        dados = {
            "categoria": "buraco",
            "subprefeitura": "santana-tucuruvi",
            "endereco": "Av. Tucuruvi, 808",
            "descricao": "Buraco grande perto do ponto de ônibus",
        }
        dados.update(campos)
        resposta = client.post("/ocorrencias", json=dados)
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    return _criar
