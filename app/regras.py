"""Regras de negócio da Zeladoria SP.

Tudo aqui é função pura (sem banco, sem HTTP) para facilitar o teste.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class Status(StrEnum):
    ABERTA = "aberta"
    EM_ANALISE = "em_analise"
    EM_EXECUCAO = "em_execucao"
    RESOLVIDA = "resolvida"
    REABERTA = "reaberta"
    CANCELADA = "cancelada"


class NivelPrioridade(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nome: str
    sla_horas: int
    peso: int


CATEGORIAS: dict[str, Categoria] = {
    c.codigo: c
    for c in (
        Categoria("alagamento", "Alagamento", sla_horas=6, peso=5),
        Categoria("arvore_risco", "Árvore com risco de queda", sla_horas=12, peso=4),
        Categoria("buraco", "Buraco na via", sla_horas=72, peso=3),
        Categoria("sinalizacao", "Semáforo ou sinalização", sla_horas=48, peso=3),
        Categoria("iluminacao", "Iluminação pública", sla_horas=48, peso=2),
        Categoria("lixo", "Lixo e entulho", sla_horas=24, peso=2),
        Categoria("calcada", "Calçada danificada", sla_horas=120, peso=1),
    )
}

# As 32 subprefeituras do município de São Paulo.
SUBPREFEITURAS: frozenset[str] = frozenset(
    {
        "aricanduva-formosa-carrao",
        "butanta",
        "campo-limpo",
        "capela-do-socorro",
        "casa-verde-cachoeirinha",
        "cidade-ademar",
        "cidade-tiradentes",
        "ermelino-matarazzo",
        "freguesia-brasilandia",
        "guaianases",
        "ipiranga",
        "itaim-paulista",
        "itaquera",
        "jabaquara",
        "jacana-tremembe",
        "lapa",
        "m-boi-mirim",
        "mooca",
        "parelheiros",
        "penha",
        "perus-anhanguera",
        "pinheiros",
        "pirituba-jaragua",
        "santana-tucuruvi",
        "santo-amaro",
        "sao-mateus",
        "sao-miguel-paulista",
        "sapopemba",
        "se",
        "vila-maria-vila-guilherme",
        "vila-mariana",
        "vila-prudente",
    }
)

BONUS_EQUIPAMENTO_SENSIVEL = 2
APOIOS_POR_PONTO = 5
BONUS_MAXIMO_APOIOS = 3

TRANSICOES: dict[Status, frozenset[Status]] = {
    Status.ABERTA: frozenset({Status.EM_ANALISE, Status.CANCELADA}),
    Status.EM_ANALISE: frozenset({Status.EM_EXECUCAO, Status.CANCELADA}),
    Status.EM_EXECUCAO: frozenset({Status.RESOLVIDA}),
    Status.RESOLVIDA: frozenset({Status.REABERTA}),
    Status.REABERTA: frozenset({Status.EM_ANALISE}),
    Status.CANCELADA: frozenset(),
}

STATUS_ENCERRADOS = frozenset({Status.RESOLVIDA, Status.CANCELADA})


class TransicaoInvalida(ValueError):
    pass


def calcular_pontos(categoria: str, proximo_equipamento_sensivel: bool, apoios: int) -> int:
    """Pontua a ocorrência: peso da categoria + perto de escola/hospital + apoio dos vizinhos."""
    pontos = CATEGORIAS[categoria].peso
    if proximo_equipamento_sensivel:
        pontos += BONUS_EQUIPAMENTO_SENSIVEL
    pontos += min(max(apoios, 0) // APOIOS_POR_PONTO, BONUS_MAXIMO_APOIOS)
    return pontos


def nivel_por_pontos(pontos: int) -> NivelPrioridade:
    if pontos >= 8:
        return NivelPrioridade.CRITICA
    if pontos >= 6:
        return NivelPrioridade.ALTA
    if pontos >= 4:
        return NivelPrioridade.MEDIA
    return NivelPrioridade.BAIXA


def calcular_prazo(categoria: str, nivel: NivelPrioridade, aberta_em: datetime) -> datetime:
    """Prazo de atendimento. Ocorrência crítica tem o SLA da categoria cortado pela metade."""
    horas = CATEGORIAS[categoria].sla_horas
    if nivel is NivelPrioridade.CRITICA:
        horas = horas / 2
    return aberta_em + timedelta(hours=horas)


def validar_transicao(atual: Status, nova: Status) -> None:
    if nova not in TRANSICOES[atual]:
        permitidos = ", ".join(sorted(s.value for s in TRANSICOES[atual])) or "nenhum"
        raise TransicaoInvalida(
            f"Não dá para ir de '{atual.value}' para '{nova.value}'. Próximos status aceitos: {permitidos}."
        )


def esta_atrasada(status: Status, prazo: datetime, agora: datetime) -> bool:
    return status not in STATUS_ENCERRADOS and agora > prazo
