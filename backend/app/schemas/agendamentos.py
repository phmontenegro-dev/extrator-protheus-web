"""
Schemas Pydantic dos endpoints /agendamentos.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.agendamento import (
    FREQUENCIAS,
    FREQ_MENSAL,
    FREQ_SEMANAL,
    PRESETS,
)


# ---------------------------------------------------------------------------
# Criação / edição
# ---------------------------------------------------------------------------

class AgendamentoCriar(BaseModel):
    """
    Payload de criação ou edição de agendamento.

    Validações:
      - frequencia ∈ FREQUENCIAS; FREQ_SEMANAL exige dias_semana; FREQ_MENSAL exige dia_mes
      - hora 0-23, minuto 0-59; dia_mes 1-28
      - preset_datas (se informado) ∈ PRESETS
    """
    nome: str = Field(min_length=1, max_length=100)
    descricao: Optional[str] = Field(default=None, max_length=500)

    tipo: str = Field(pattern=r"^(relatorio_pronto|relatorio_livre|codigo_sql)$")
    relatorio_id: str = Field(min_length=1, max_length=100)

    filtros_base: Optional[dict] = None
    sql_texto: Optional[str] = Field(default=None, max_length=50_000)
    preset_datas: Optional[str] = None

    frequencia: str
    dias_semana: Optional[list[int]] = None
    dia_mes: Optional[int] = Field(default=None, ge=1, le=28)
    hora: int = Field(ge=0, le=23)
    minuto: int = Field(default=0, ge=0, le=59)

    ativo: bool = True
    estrategia_nome: str = Field(default="padrao", pattern=r"^(padrao|sobrescrever)$")
    retencao_dias: int = Field(default=7, ge=1, le=90)

    @model_validator(mode="after")
    def _valida(self):
        if self.frequencia not in FREQUENCIAS:
            raise ValueError(f"frequencia inválida: {self.frequencia!r}")

        if self.frequencia == FREQ_SEMANAL:
            if not self.dias_semana:
                raise ValueError("frequencia 'semanal' exige dias_semana (1=seg..7=dom)")
            for d in self.dias_semana:
                if not 1 <= int(d) <= 7:
                    raise ValueError("dias_semana devem estar entre 1 e 7")
        elif self.dias_semana:
            raise ValueError("dias_semana só se aplica a frequencia 'semanal'")

        if self.frequencia == FREQ_MENSAL:
            if not self.dia_mes:
                raise ValueError("frequencia 'mensal' exige dia_mes (1..28)")
        elif self.dia_mes is not None:
            raise ValueError("dia_mes só se aplica a frequencia 'mensal'")

        if self.preset_datas is not None and self.preset_datas not in PRESETS:
            raise ValueError(f"preset_datas inválido: {self.preset_datas!r}")

        if self.tipo == "codigo_sql" and not (self.sql_texto or "").strip():
            raise ValueError("tipo 'codigo_sql' exige sql_texto")

        return self


# ---------------------------------------------------------------------------
# Resposta
# ---------------------------------------------------------------------------

class AgendamentoResumo(BaseModel):
    """Resposta da listagem e detalhes."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    username: Optional[str]
    nome: str
    descricao: Optional[str]
    tipo: str
    relatorio_id: str
    filtros_base: Optional[dict]
    sql_texto: Optional[str]
    preset_datas: Optional[str]
    frequencia: str
    dias_semana: Optional[list[int]]
    dia_mes: Optional[int]
    hora: int
    minuto: int
    ativo: bool
    proxima_execucao: Optional[datetime]
    ultima_execucao: Optional[datetime]
    estrategia_nome: str
    retencao_dias: int
    token_prefixo: Optional[str]
    criado_em: datetime
    atualizado_em: datetime


class AgendamentoCriadoResponse(AgendamentoResumo):
    """
    Devolvido no POST /agendamentos — inclui o token em claro UMA vez.
    Se o usuário perder, precisa regenerar via POST /agendamentos/{id}/regenerar-token.
    """
    token_claro: str


# ---------------------------------------------------------------------------
# Execuções
# ---------------------------------------------------------------------------

class ExecucaoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agendamento_id: int
    job_id: Optional[str]
    status: str
    params_resolvidos: Optional[dict]
    total_linhas: Optional[int]
    tamanho_bytes: Optional[int]
    nome_arquivo: Optional[str]
    erro_mensagem: Optional[str]
    baixada_por: Optional[list[str]]
    criado_em: datetime
    concluido_em: Optional[datetime]


class ExecucaoPendenteParaScript(BaseModel):
    """
    Resposta de GET /agendamentos/{id}/execucoes/pendentes — formato
    enxuto que o script sincronizador usa pra baixar os CSVs.
    """
    id: int
    nome_arquivo: Optional[str]
    tamanho_bytes: Optional[int]
    total_linhas: Optional[int]
    concluido_em: Optional[datetime]
    download_url: str   # URL relativa; script prefixa com o host configurado


class CallbackDownload(BaseModel):
    """Payload POST /agendamentos/{id}/execucoes/{exec_id}/baixada."""
    maquina_id: str = Field(min_length=1, max_length=100)
    ok: bool = True
    erro: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Script gerado
# ---------------------------------------------------------------------------

class ScriptGerado(BaseModel):
    """Resposta de GET /agendamentos/{id}/script?os=windows."""
    nome_arquivo: str      # extrator-sync-<id>.py (ou .ps1 no futuro)
    conteudo: str          # o texto do script
    instrucoes: str        # markdown com passo a passo
    extensao: str          # "py", "ps1", "sh"
