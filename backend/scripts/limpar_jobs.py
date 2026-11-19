"""
Varredura de jobs expirados.

Executa diariamente via cron:
    # /etc/cron.d/extrator-jobs (uma linha, roda 3x ao dia):
    15 3,11,19 * * * extrator cd /opt/extrator-protheus/backend && \
        .venv/bin/python scripts/limpar_jobs.py >> /var/log/extrator/limpar_jobs.log 2>&1

O que faz:
  - deleta JobExtracao cujo concluido_em < now - JOBS_RETENCAO_DIAS
  - remove os CSVs correspondentes do disco (/var/lib/extrator/jobs/)
  - deixa um resumo no stdout (quantos deletou, quanto liberou em MB)

Também marca como erro jobs "zumbis" — presos em status ativo mas cujo
iniciado_em é muito antigo (indicador de que o processo foi derrubado
no meio).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Suporta rodar como "python scripts/limpar_jobs.py" (sem instalar o pacote).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.jobs.watchdog import marcar_zumbis_agora  # noqa: E402
from app.models.job import JobExtracao  # noqa: E402

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("limpar_jobs")


def _marcar_zumbis(db) -> int:
    """
    Delega pro watchdog central (app/jobs/watchdog.py). Ele já roda a cada
    60s via scheduler, então quando este script roda (3x/dia) geralmente
    não tem nada pra marcar — fica como safety net.
    """
    return marcar_zumbis_agora(db)


def _apagar_expirados(db, pasta_jobs: Path, dias: int) -> tuple[int, int]:
    """
    Apaga JobExtracao concluído/erro/cancelado antigo + seu CSV em disco.
    Retorna (qtd_deletada, bytes_liberados).
    """
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    antigos = (
        db.query(JobExtracao)
        .filter(JobExtracao.concluido_em.isnot(None))
        .filter(JobExtracao.concluido_em < limite)
        .all()
    )
    bytes_liberados = 0
    for j in antigos:
        if j.caminho_csv:
            try:
                tam = os.path.getsize(j.caminho_csv)
                os.remove(j.caminho_csv)
                bytes_liberados += tam
            except FileNotFoundError:
                pass
            except Exception:
                log.exception("falha ao apagar %s", j.caminho_csv)
        db.delete(j)
    if antigos:
        db.commit()
    return len(antigos), bytes_liberados


def _limpar_orfaos(db, pasta_jobs: Path) -> int:
    """
    CSVs em disco cujo job_id não está mais no banco. Varredura defensiva pra
    cobrir casos de erro de FS vs commit.
    """
    if not pasta_jobs.exists():
        return 0
    jobs_atuais = {row[0] for row in db.query(JobExtracao.id).all()}
    removidos = 0
    for arq in pasta_jobs.glob("*.csv"):
        job_id = arq.stem
        if job_id not in jobs_atuais:
            try:
                arq.unlink()
                removidos += 1
            except Exception:
                log.exception("falha ao remover órfão %s", arq)
    return removidos


def main() -> int:
    settings = get_settings()
    pasta_jobs = Path(settings.pasta_jobs)
    log.info("iniciando limpeza em %s", pasta_jobs)

    db = SessionLocal()
    try:
        zumbis = _marcar_zumbis(db)
        if zumbis:
            log.info("marcados como erro: %d job(s) zumbi", zumbis)

        qtd, b = _apagar_expirados(db, pasta_jobs, settings.jobs_retencao_dias)
        log.info("expirados: %d job(s), %.1f MB liberados", qtd, b / 1024 / 1024)

        orfaos = _limpar_orfaos(db, pasta_jobs)
        if orfaos:
            log.info("CSVs órfãos removidos: %d", orfaos)
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
