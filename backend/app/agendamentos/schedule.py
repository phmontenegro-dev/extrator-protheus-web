"""
Cálculo de próxima execução de um Agendamento.

Dado (frequencia, dias_semana, dia_mes, hora, minuto) e o "agora" em BRT,
devolve o próximo datetime UTC em que o agendamento deve disparar.

Por que UTC? Porque o banco guarda `proxima_execucao` como DateTime(tz=True)
e o scheduler compara com `datetime.now(utc)`. Cálculo é feito em BRT
(sensato pro usuário) e convertido no final.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.agendamentos.datas import TZ_BRT
from app.models.agendamento import (
    FREQ_DIARIO,
    FREQ_MENSAL,
    FREQ_SEMANAL,
    Agendamento,
)


def _combinar(d: date, hora: int, minuto: int) -> datetime:
    """Datetime BRT de (d, hora, minuto). Cai pra UTC se TZ indisponível."""
    if TZ_BRT:
        return datetime(d.year, d.month, d.day, hora, minuto, tzinfo=TZ_BRT)
    return datetime(d.year, d.month, d.day, hora, minuto, tzinfo=timezone.utc)


def _agora_brt() -> datetime:
    return datetime.now(TZ_BRT) if TZ_BRT else datetime.now(timezone.utc)


def _para_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def calcular_proxima_execucao(
    ag: Agendamento,
    *,
    agora: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Próxima execução (em UTC) a partir de `agora` (default: now BRT).

    Retorna None se o agendamento está em estado incoerente (ex: semanal sem
    dias_semana) — nesse caso o scheduler ignora até a config ser corrigida.
    `agora` em TZ-aware; se None, usa agora em BRT.
    """
    if agora is None:
        agora = _agora_brt()
    elif TZ_BRT:
        agora = agora.astimezone(TZ_BRT)

    hoje = agora.date()

    if ag.frequencia == FREQ_DIARIO:
        # Candidato: hoje às HH:MM
        cand = _combinar(hoje, ag.hora, ag.minuto)
        if cand <= agora:
            cand = _combinar(hoje + timedelta(days=1), ag.hora, ag.minuto)
        return _para_utc(cand)

    if ag.frequencia == FREQ_SEMANAL:
        dias = ag.dias_semana or []
        # dias no ISO: 1=seg...7=dom. weekday() retorna 0=seg...6=dom. Normalizamos.
        dias_norm = {int(d) - 1 for d in dias if 1 <= int(d) <= 7}
        if not dias_norm:
            return None
        # Tenta hoje e os próximos 7 dias, pega o primeiro que bate.
        for delta in range(0, 8):
            d = hoje + timedelta(days=delta)
            if d.weekday() not in dias_norm:
                continue
            cand = _combinar(d, ag.hora, ag.minuto)
            if cand > agora:
                return _para_utc(cand)
        return None  # não deveria acontecer

    if ag.frequencia == FREQ_MENSAL:
        if not ag.dia_mes or not (1 <= ag.dia_mes <= 28):
            return None
        # Candidato: dia_mes do mês atual
        try:
            cand_atual = _combinar(hoje.replace(day=ag.dia_mes), ag.hora, ag.minuto)
        except ValueError:
            cand_atual = None
        if cand_atual and cand_atual > agora:
            return _para_utc(cand_atual)
        # Próximo mês
        prox_mes = hoje.replace(day=1) + timedelta(days=32)
        cand_prox = _combinar(prox_mes.replace(day=ag.dia_mes), ag.hora, ag.minuto)
        return _para_utc(cand_prox)

    return None
