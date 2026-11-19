"""
Resolve presets de datas relativas para (data_inicio, data_fim) em YYYYMMDD.

Todos os cálculos usam o fuso **America/Sao_Paulo** (fixo na Etapa 14).
A "data de hoje" é a data local, não UTC — importante porque uma execução
rodando às 00:30 BRT de 20/nov deve interpretar "ontem" como 19/nov, não
19/nov ou 20/nov dependendo do UTC do servidor.

Os presets são resolvidos no momento do disparo, não quando o agendamento
é criado — isso é o ponto desse módulo.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from app.models.agendamento import (
    PRESET_MES_ANTERIOR,
    PRESET_MES_ATUAL_ATE_ONTEM,
    PRESET_ONTEM,
    PRESET_SEMANA_ANTERIOR,
    PRESET_ULTIMOS_7,
    PRESET_ULTIMOS_30,
)


TZ_BRT = ZoneInfo("America/Sao_Paulo") if ZoneInfo else None


def hoje_local() -> date:
    """Data de hoje em America/Sao_Paulo (independe do TZ do servidor)."""
    if TZ_BRT is None:
        return date.today()
    return datetime.now(TZ_BRT).date()


def _aaaammdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _primeiro_dia_mes(d: date) -> date:
    return d.replace(day=1)


def _ultimo_dia_mes_anterior(d: date) -> date:
    """Último dia do mês ANTERIOR a `d`."""
    return _primeiro_dia_mes(d) - timedelta(days=1)


def calcular_datas_do_preset(
    preset: Optional[str],
    *,
    hoje: Optional[date] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve o preset em (data_inicio, data_fim) no formato Protheus (YYYYMMDD).

    Retorna (None, None) quando:
      - preset é None (relatório sem filtro de data: SB8, SD1, SD2 Suzano)
      - preset é desconhecido (nunca deveria acontecer se validação funcionou)

    `hoje` sobrescrevível pra testes.
    """
    if not preset:
        return None, None

    if hoje is None:
        hoje = hoje_local()

    if preset == PRESET_ONTEM:
        d = hoje - timedelta(days=1)
        return _aaaammdd(d), _aaaammdd(d)

    if preset == PRESET_ULTIMOS_7:
        # últimos 7 dias completos (ontem inclusive até 7 dias atrás)
        fim = hoje - timedelta(days=1)
        ini = hoje - timedelta(days=7)
        return _aaaammdd(ini), _aaaammdd(fim)

    if preset == PRESET_ULTIMOS_30:
        fim = hoje - timedelta(days=1)
        ini = hoje - timedelta(days=30)
        return _aaaammdd(ini), _aaaammdd(fim)

    if preset == PRESET_SEMANA_ANTERIOR:
        # Segunda(ISO=1) à domingo(ISO=7) da semana anterior
        # weekday(): 0=seg, 6=dom
        dias_desde_segunda = hoje.weekday()        # 0 se hoje é seg, 6 se dom
        segunda_atual = hoje - timedelta(days=dias_desde_segunda)
        dom_anterior = segunda_atual - timedelta(days=1)
        seg_anterior = dom_anterior - timedelta(days=6)
        return _aaaammdd(seg_anterior), _aaaammdd(dom_anterior)

    if preset == PRESET_MES_ANTERIOR:
        fim = _ultimo_dia_mes_anterior(hoje)
        ini = _primeiro_dia_mes(fim)
        return _aaaammdd(ini), _aaaammdd(fim)

    if preset == PRESET_MES_ATUAL_ATE_ONTEM:
        ini = _primeiro_dia_mes(hoje)
        fim = hoje - timedelta(days=1)
        if fim < ini:
            # Hoje é dia 1: o intervalo vira o próprio dia 1 anterior pra não
            # mandar período inválido pro Protheus. Trata como o ONTEM.
            fim = ini
        return _aaaammdd(ini), _aaaammdd(fim)

    return None, None


# Descrições humanas pros presets, usadas no frontend.
PRESETS_LABEL = {
    PRESET_ONTEM: "Ontem",
    PRESET_ULTIMOS_7: "Últimos 7 dias",
    PRESET_ULTIMOS_30: "Últimos 30 dias",
    PRESET_SEMANA_ANTERIOR: "Semana anterior (seg a dom)",
    PRESET_MES_ANTERIOR: "Mês anterior (completo)",
    PRESET_MES_ATUAL_ATE_ONTEM: "Mês atual até ontem",
}
