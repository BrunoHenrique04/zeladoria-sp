from datetime import UTC, datetime, timedelta

import pytest

from app import regras
from app.regras import NivelPrioridade, Status

INICIO = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)


def test_sao_paulo_tem_32_subprefeituras():
    assert len(regras.SUBPREFEITURAS) == 32


@pytest.mark.parametrize(
    ("categoria", "sensivel", "apoios", "esperado"),
    [
        ("calcada", False, 0, 1),
        ("buraco", True, 0, 5),
        ("buraco", False, 4, 3),
        ("buraco", False, 5, 4),
        ("buraco", False, 100, 6),  # bônus de apoio para em +3
        ("alagamento", True, 15, 10),
        ("lixo", False, -3, 2),
    ],
)
def test_calcular_pontos(categoria, sensivel, apoios, esperado):
    assert regras.calcular_pontos(categoria, sensivel, apoios) == esperado


@pytest.mark.parametrize(
    ("pontos", "nivel"),
    [
        (1, NivelPrioridade.BAIXA),
        (3, NivelPrioridade.BAIXA),
        (4, NivelPrioridade.MEDIA),
        (5, NivelPrioridade.MEDIA),
        (6, NivelPrioridade.ALTA),
        (7, NivelPrioridade.ALTA),
        (8, NivelPrioridade.CRITICA),
        (12, NivelPrioridade.CRITICA),
    ],
)
def test_nivel_por_pontos(pontos, nivel):
    assert regras.nivel_por_pontos(pontos) is nivel


def test_prazo_usa_sla_da_categoria():
    prazo = regras.calcular_prazo("buraco", NivelPrioridade.MEDIA, INICIO)
    assert prazo - INICIO == timedelta(hours=72)


def test_prazo_cai_pela_metade_quando_critica():
    prazo = regras.calcular_prazo("alagamento", NivelPrioridade.CRITICA, INICIO)
    assert prazo - INICIO == timedelta(hours=3)


@pytest.mark.parametrize(
    ("atual", "nova"),
    [
        (Status.ABERTA, Status.EM_ANALISE),
        (Status.EM_ANALISE, Status.EM_EXECUCAO),
        (Status.EM_EXECUCAO, Status.RESOLVIDA),
        (Status.RESOLVIDA, Status.REABERTA),
        (Status.REABERTA, Status.EM_ANALISE),
        (Status.ABERTA, Status.CANCELADA),
    ],
)
def test_transicoes_permitidas(atual, nova):
    regras.validar_transicao(atual, nova)


@pytest.mark.parametrize(
    ("atual", "nova"),
    [
        (Status.ABERTA, Status.RESOLVIDA),
        (Status.EM_EXECUCAO, Status.CANCELADA),
        (Status.CANCELADA, Status.ABERTA),
        (Status.RESOLVIDA, Status.EM_EXECUCAO),
    ],
)
def test_transicoes_bloqueadas(atual, nova):
    with pytest.raises(regras.TransicaoInvalida):
        regras.validar_transicao(atual, nova)


def test_mensagem_de_cancelada_diz_que_nao_ha_saida():
    with pytest.raises(regras.TransicaoInvalida, match="nenhum"):
        regras.validar_transicao(Status.CANCELADA, Status.ABERTA)


def test_atraso():
    prazo = INICIO + timedelta(hours=1)
    depois = INICIO + timedelta(hours=2)
    assert regras.esta_atrasada(Status.ABERTA, prazo, depois)
    assert not regras.esta_atrasada(Status.ABERTA, prazo, INICIO)
    assert not regras.esta_atrasada(Status.RESOLVIDA, prazo, depois)
    assert not regras.esta_atrasada(Status.CANCELADA, prazo, depois)
