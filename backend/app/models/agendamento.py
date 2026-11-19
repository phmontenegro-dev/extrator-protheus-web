"""
Agendamento de execução recorrente de relatórios (Etapa 14).

Cada agendamento tem:
  - um relatório alvo (pronto, livre ou SQL)
  - parâmetros base (filtros não-temporais, SQL, lista de colunas)
  - preset de datas relativas (ontem, últimos 7, mês anterior, etc.) — resolvido
    no momento do disparo
  - uma frequência (diário/semanal/mensal) + hora do dia
  - um token de API hasheado, usado pelo script sincronizador no PC do usuário
  - toggle ativo/inativo

O scheduler systemd (`extrator-scheduler.service`) lê linhas com
`ativo=True` e `proxima_execucao <= now()`, dispara um JobExtracao via
executor, registra uma AgendamentoExecucao e recalcula `proxima_execucao`.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---- Frequências -----------------------------------------------------------

FREQ_DIARIO = "diario"
FREQ_SEMANAL = "semanal"     # usa dias_semana (ISO: 1=seg...7=dom)
FREQ_MENSAL = "mensal"       # usa dia_mes (1..28, pra não explodir em fevereiro)

FREQUENCIAS = {FREQ_DIARIO, FREQ_SEMANAL, FREQ_MENSAL}

# ---- Presets de data relativa ---------------------------------------------
# Resolvidos pela função calcular_datas_do_preset na hora do disparo.

PRESET_ONTEM = "ontem"
PRESET_ULTIMOS_7 = "ultimos_7"
PRESET_ULTIMOS_30 = "ultimos_30"
PRESET_SEMANA_ANTERIOR = "semana_anterior"      # seg-dom da semana anterior
PRESET_MES_ANTERIOR = "mes_anterior"            # mês cheio anterior
PRESET_MES_ATUAL_ATE_ONTEM = "mes_atual_ate_ontem"

PRESETS = {
    PRESET_ONTEM,
    PRESET_ULTIMOS_7,
    PRESET_ULTIMOS_30,
    PRESET_SEMANA_ANTERIOR,
    PRESET_MES_ANTERIOR,
    PRESET_MES_ATUAL_ATE_ONTEM,
}

# ---- Estratégia de nome de arquivo no disco ------------------------------

NOME_PADRAO = "padrao"          # <relatorio>_<data_execucao>.csv
NOME_SOBRESCREVER = "sobrescrever"   # mesmo nome sempre: <relatorio>.csv


class Agendamento(Base):
    """
    Configuração persistente de uma execução recorrente.
    """
    __tablename__ = "agendamentos"

    id: Mapped[int] = mapped_column(primary_key=True)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Guardado solto também — sobrevive a eventual deleção do usuário.
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Tipo / id de relatório — mesma convenção da Etapa 11.
    #   tipo = "relatorio_pronto" | "relatorio_livre" | "codigo_sql"
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    relatorio_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Filtros base (filial, colunas, tabela) — SEM as datas, que são resolvidas
    # do preset. SQL da tela Código SQL vai em sql_texto.
    filtros_base: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sql_texto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Preset de datas relativas. Pode ser None pra relatórios sem data (SB8, SD1, SD2 Suzano).
    preset_datas: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # ---- Agenda ----
    frequencia: Mapped[str] = mapped_column(String(20), nullable=False)
    # Para FREQ_SEMANAL: lista de ints [1..7] (1=seg, 7=dom). Ex: [1,3,5]
    dias_semana: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # Para FREQ_MENSAL: dia do mês 1..28.
    dia_mes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Hora/minuto do disparo no fuso America/Sao_Paulo (fixo, Etapa 14).
    hora: Mapped[int] = mapped_column(Integer, nullable=False)
    minuto: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ---- Estado ----
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    proxima_execucao: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ultima_execucao: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Entrega / nome de arquivo ----
    estrategia_nome: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NOME_PADRAO, server_default=NOME_PADRAO,
    )
    # Dias que a execução/CSV ficam disponíveis no servidor antes do cleanup.
    retencao_dias: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7, server_default="7",
    )

    # ---- Token de API (usado pelo script sincronizador no PC) ----
    # Guardamos só o hash (bcrypt). O token em claro é mostrado UMA vez na UI
    # quando criado — se perder, revoga/regenera.
    token_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Primeiros chars em claro, pra identificar na UI: "sk_ag_8f3d..." .
    token_prefixo: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Agendamento id={self.id} nome={self.nome!r} freq={self.frequencia!r}>"


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

EXEC_PENDENTE = "pendente"       # disparada, aguardando job rodar
EXEC_CONCLUIDA = "concluida"     # job terminou com CSV disponível
EXEC_ERRO = "erro"
EXEC_CANCELADA = "cancelada"

EXEC_STATUS = {EXEC_PENDENTE, EXEC_CONCLUIDA, EXEC_ERRO, EXEC_CANCELADA}


class AgendamentoExecucao(Base):
    """
    Uma execução concreta de um Agendamento.

    Vinculada a um JobExtracao (que é o motor de execução). Status é derivado
    do status do job: o dispatcher atualiza esta linha quando o job termina.

    `baixada_por` é um JSON array de IDs de máquina (string curta tipo
    "pedro-notebook-abcd"). O script sincronizador manda esse ID no callback
    após baixar com sucesso — assim conseguimos entregar a mesma execução pra
    2+ máquinas do mesmo usuário (etapa H=a).
    """
    __tablename__ = "agendamentos_execucoes"

    id: Mapped[int] = mapped_column(primary_key=True)

    agendamento_id: Mapped[int] = mapped_column(
        ForeignKey("agendamentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("jobs_extracao.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EXEC_PENDENTE, server_default=EXEC_PENDENTE, index=True
    )

    # Snapshot dos parâmetros efetivamente usados neste disparo
    # (inclui data_inicio/data_fim calculadas do preset).
    params_resolvidos: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Resultado (preenchido quando o job conclui)
    total_linhas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tamanho_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nome_arquivo: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    erro_mensagem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Lista de maquina_ids que já baixaram (multi-PC).
    baixada_por: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, default=list, server_default="[]"
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    concluido_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AgendamentoExecucao id={self.id} agendamento={self.agendamento_id} status={self.status!r}>"
