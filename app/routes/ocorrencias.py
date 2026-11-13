from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import regras
from app.database import get_db
from app.models import Ocorrencia, agora_utc, com_fuso
from app.schemas import Metricas, MudancaStatus, OcorrenciaEntrada, OcorrenciaSaida

router = APIRouter(prefix="/ocorrencias", tags=["ocorrências"])

DB = Annotated[Session, Depends(get_db)]


def _saida(ocorrencia: Ocorrencia) -> OcorrenciaSaida:
    saida = OcorrenciaSaida.model_validate(ocorrencia)
    saida.atrasada = regras.esta_atrasada(
        regras.Status(ocorrencia.status), com_fuso(ocorrencia.prazo_sla), agora_utc()
    )
    return saida


def _buscar(db: Session, ocorrencia_id: int) -> Ocorrencia:
    ocorrencia = db.get(Ocorrencia, ocorrencia_id)
    if ocorrencia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ocorrência não encontrada")
    return ocorrencia


def _repriorizar(ocorrencia: Ocorrencia) -> None:
    ocorrencia.pontos = regras.calcular_pontos(
        ocorrencia.categoria, ocorrencia.proximo_equipamento_sensivel, ocorrencia.apoios
    )
    nivel = regras.nivel_por_pontos(ocorrencia.pontos)
    ocorrencia.prioridade = nivel.value
    ocorrencia.prazo_sla = regras.calcular_prazo(ocorrencia.categoria, nivel, com_fuso(ocorrencia.aberta_em))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OcorrenciaSaida)
def abrir_ocorrencia(dados: OcorrenciaEntrada, db: DB) -> OcorrenciaSaida:
    agora = agora_utc()
    ocorrencia = Ocorrencia(
        **dados.model_dump(),
        apoios=0,
        status=regras.Status.ABERTA.value,
        aberta_em=agora,
        atualizada_em=agora,
    )
    _repriorizar(ocorrencia)
    db.add(ocorrencia)
    db.commit()
    db.refresh(ocorrencia)
    return _saida(ocorrencia)


@router.get("", response_model=list[OcorrenciaSaida])
def listar_ocorrencias(
    db: DB,
    status_: Annotated[regras.Status | None, Query(alias="status")] = None,
    subprefeitura: str | None = None,
    categoria: str | None = None,
    somente_atrasadas: bool = False,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[OcorrenciaSaida]:
    consulta = select(Ocorrencia).order_by(Ocorrencia.pontos.desc(), Ocorrencia.aberta_em)
    if status_:
        consulta = consulta.where(Ocorrencia.status == status_.value)
    if subprefeitura:
        consulta = consulta.where(Ocorrencia.subprefeitura == subprefeitura)
    if categoria:
        consulta = consulta.where(Ocorrencia.categoria == categoria)

    resultado = [_saida(o) for o in db.scalars(consulta)]
    if somente_atrasadas:
        resultado = [o for o in resultado if o.atrasada]
    return resultado[:limite]


@router.get("/metricas", response_model=Metricas)
def metricas(db: DB) -> Metricas:
    ocorrencias = list(db.scalars(select(Ocorrencia)))
    agora = agora_utc()

    resolvidas = [o for o in ocorrencias if o.resolvida_em is not None]
    no_prazo = [o for o in resolvidas if com_fuso(o.resolvida_em) <= com_fuso(o.prazo_sla)]
    pct = round(100 * len(no_prazo) / len(resolvidas), 1) if resolvidas else None

    return Metricas(
        total=len(ocorrencias),
        por_status=dict(Counter(o.status for o in ocorrencias)),
        por_prioridade=dict(Counter(o.prioridade for o in ocorrencias)),
        abertas_atrasadas=sum(
            regras.esta_atrasada(regras.Status(o.status), com_fuso(o.prazo_sla), agora) for o in ocorrencias
        ),
        resolvidas_no_prazo_pct=pct,
    )


@router.get("/{ocorrencia_id}", response_model=OcorrenciaSaida)
def detalhar_ocorrencia(ocorrencia_id: int, db: DB) -> OcorrenciaSaida:
    return _saida(_buscar(db, ocorrencia_id))


@router.patch("/{ocorrencia_id}/status", response_model=OcorrenciaSaida)
def mudar_status(ocorrencia_id: int, mudanca: MudancaStatus, db: DB) -> OcorrenciaSaida:
    ocorrencia = _buscar(db, ocorrencia_id)
    try:
        regras.validar_transicao(regras.Status(ocorrencia.status), mudanca.status)
    except regras.TransicaoInvalida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from erro

    agora = agora_utc()
    ocorrencia.status = mudanca.status.value
    ocorrencia.atualizada_em = agora
    if mudanca.status is regras.Status.RESOLVIDA:
        ocorrencia.resolvida_em = agora
    elif mudanca.status is regras.Status.REABERTA:
        ocorrencia.resolvida_em = None

    db.commit()
    db.refresh(ocorrencia)
    return _saida(ocorrencia)


@router.post("/{ocorrencia_id}/apoios", response_model=OcorrenciaSaida)
def apoiar_ocorrencia(ocorrencia_id: int, db: DB) -> OcorrenciaSaida:
    """Um vizinho confirma o problema. A cada 5 apoios a prioridade sobe um ponto (até 3)."""
    ocorrencia = _buscar(db, ocorrencia_id)
    if regras.Status(ocorrencia.status) in regras.STATUS_ENCERRADOS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ocorrência encerrada não recebe apoio")

    ocorrencia.apoios += 1
    ocorrencia.atualizada_em = agora_utc()
    _repriorizar(ocorrencia)
    db.commit()
    db.refresh(ocorrencia)
    return _saida(ocorrencia)
