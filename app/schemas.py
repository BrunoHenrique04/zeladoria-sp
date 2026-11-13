from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.regras import CATEGORIAS, SUBPREFEITURAS, Status


class OcorrenciaEntrada(BaseModel):
    categoria: str = Field(examples=["buraco"])
    subprefeitura: str = Field(examples=["santana-tucuruvi"])
    endereco: str = Field(min_length=5, max_length=200, examples=["Av. Tucuruvi, 808"])
    descricao: str = Field(min_length=10, max_length=2000)
    proximo_equipamento_sensivel: bool = Field(
        default=False, description="Fica perto de escola, hospital ou UBS?"
    )

    @field_validator("categoria")
    @classmethod
    def categoria_conhecida(cls, valor: str) -> str:
        if valor not in CATEGORIAS:
            raise ValueError(f"categoria desconhecida. Use uma destas: {', '.join(sorted(CATEGORIAS))}")
        return valor

    @field_validator("subprefeitura")
    @classmethod
    def subprefeitura_valida(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if valor not in SUBPREFEITURAS:
            raise ValueError("subprefeitura não existe. Consulte GET /subprefeituras")
        return valor


class OcorrenciaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    categoria: str
    subprefeitura: str
    endereco: str
    descricao: str
    proximo_equipamento_sensivel: bool
    apoios: int
    pontos: int
    prioridade: str
    status: str
    aberta_em: datetime
    prazo_sla: datetime
    atualizada_em: datetime
    resolvida_em: datetime | None = None
    atrasada: bool = False


class MudancaStatus(BaseModel):
    status: Status


class CategoriaSaida(BaseModel):
    codigo: str
    nome: str
    sla_horas: int
    peso: int


class Metricas(BaseModel):
    total: int
    por_status: dict[str, int]
    por_prioridade: dict[str, int]
    abertas_atrasadas: int
    resolvidas_no_prazo_pct: float | None
