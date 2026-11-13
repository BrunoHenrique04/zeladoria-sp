from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def agora_utc() -> datetime:
    return datetime.now(UTC)


class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria: Mapped[str] = mapped_column(String(32), index=True)
    subprefeitura: Mapped[str] = mapped_column(String(48), index=True)
    endereco: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text)
    proximo_equipamento_sensivel: Mapped[bool] = mapped_column(Boolean, default=False)
    apoios: Mapped[int] = mapped_column(Integer, default=0)
    pontos: Mapped[int] = mapped_column(Integer)
    prioridade: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    aberta_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    prazo_sla: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def com_fuso(valor: datetime) -> datetime:
    """SQLite devolve datetime sem fuso; o Postgres devolve com. Padroniza em UTC."""
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)
