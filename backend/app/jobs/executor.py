"""
Executor de jobs de extração.

Roda em segundo plano como um ThreadPoolExecutor global, iniciado no
startup do FastAPI. A ideia é simples:

  enqueue(job, runner) → thread pool pega → runner atualiza status no banco
                       → progress thread atualiza pct a cada 2s
                       → ao terminar, status final + CSV em disco

Garantias:
  - cada thread tem SUA PRÓPRIA sessão SQLAlchemy (sessões não são thread-safe)
  - uma só fila pro processo inteiro, limitada por `jobs_max_workers`
  - limite de N jobs ATIVOS por usuário é checado no enqueue (não aqui)
  - cada job tem uma thread separada que atualiza progresso sem bloquear
    a thread que está rodando a query

O executor NÃO conhece a lógica de cada relatório. Quem sabe extrair e
tratar é o `runner` que recebe o job e o objeto com os helpers de status.
"""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from app.config import get_settings
from app.database import SessionLocal
from app.jobs.eta import progresso_estimado
from app.models.job import (
    STATUS_ATIVOS,
    STATUS_CANCELADO,
    STATUS_CONCLUIDO,
    STATUS_CONECTANDO,
    STATUS_ERRO,
    STATUS_PENDENTE,
    JobExtracao,
)

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Singleton do executor
# -----------------------------------------------------------------------------

class _JobsRuntime:
    """Mantém o pool global, as threads de progresso e o lock de concorrência."""

    def __init__(self) -> None:
        self.pool: Optional[ThreadPoolExecutor] = None
        self.lock = threading.Lock()  # protege `progress_threads`
        self.progress_threads: dict[str, threading.Event] = {}  # job_id → stop event

    def iniciar(self, max_workers: int) -> None:
        if self.pool is None:
            self.pool = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="job-worker"
            )
            log.info("executor de jobs iniciado com %d workers", max_workers)

    def desligar(self) -> None:
        if self.pool is not None:
            # Sinaliza todas as threads de progresso pra pararem.
            with self.lock:
                for ev in self.progress_threads.values():
                    ev.set()
                self.progress_threads.clear()
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.pool = None
            log.info("executor de jobs desligado")


_runtime = _JobsRuntime()


def iniciar_executor() -> None:
    """Chamado no startup do FastAPI."""
    settings = get_settings()
    _runtime.iniciar(settings.jobs_max_workers)
    # Tenta criar a pasta de jobs. Se não puder (permissão), loga e segue —
    # o erro vai aparecer no primeiro job criado, não no boot. Isso deixa o
    # app subir mesmo em dev onde /var/lib/extrator não existe.
    try:
        Path(settings.pasta_jobs).mkdir(parents=True, exist_ok=True)
    except Exception:
        log.warning(
            "não foi possível criar PASTA_JOBS=%s — jobs assíncronos vão falhar "
            "até a pasta existir e ser gravável",
            settings.pasta_jobs,
        )


def desligar_executor() -> None:
    """Chamado no shutdown do FastAPI."""
    _runtime.desligar()


# -----------------------------------------------------------------------------
# Helpers que o runner usa pra atualizar o status
# -----------------------------------------------------------------------------

@contextmanager
def _sessao_thread():
    """Sessão SQLAlchemy curta, pra uso dentro das threads do pool."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _atualizar_status(job_id: str, **campos) -> None:
    """Patch nos campos do job, isolando a sessão da thread do worker."""
    with _sessao_thread() as db:
        job = db.get(JobExtracao, job_id)
        if job is None:
            return
        for k, v in campos.items():
            setattr(job, k, v)
        db.commit()


class JobContext:
    """
    Objeto repassado ao runner pra ele avançar status/progresso sem
    se preocupar com sessão SQLAlchemy ou threads.

    O runner chama:
        ctx.avancar("consultando")  # muda status
        # ... faz o trabalho longo ...
        ctx.finalizar_sucesso(caminho_csv, nome_arquivo, total_linhas, tamanho_bytes)
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def avancar(self, status: str) -> None:
        _atualizar_status(self.job_id, status=status)

    def finalizar_sucesso(
        self,
        caminho_csv: str,
        nome_arquivo: str,
        total_linhas: int,
        tamanho_bytes: int,
    ) -> None:
        _atualizar_status(
            self.job_id,
            status=STATUS_CONCLUIDO,
            progresso_pct=100,
            caminho_csv=caminho_csv,
            nome_arquivo=nome_arquivo,
            total_linhas=total_linhas,
            tamanho_bytes=tamanho_bytes,
            concluido_em=datetime.now(timezone.utc),
        )

    def finalizar_erro(self, mensagem: str) -> None:
        _atualizar_status(
            self.job_id,
            status=STATUS_ERRO,
            erro_mensagem=mensagem[:2000],
            concluido_em=datetime.now(timezone.utc),
        )


# -----------------------------------------------------------------------------
# Thread de progresso: atualiza pct a cada 2s enquanto o job estiver ativo
# -----------------------------------------------------------------------------

def _loop_progresso(job_id: str, stop_event: threading.Event) -> None:
    """
    Thread leve que roda em paralelo ao job pra:
      1. atualizar `progresso_pct` baseado no ETA
      2. atualizar `heartbeat_em` a cada tick (watchdog usa isso pra
         detectar jobs zumbis — worker morreu sem marcar status final)

    Para quando o stop_event dispara OU quando o status vira final.
    """
    while not stop_event.is_set():
        try:
            with _sessao_thread() as db:
                job = db.get(JobExtracao, job_id)
                if job is None:
                    return
                if job.status not in STATUS_ATIVOS:
                    return

                # Heartbeat — sempre. Mesmo sem ETA, isso prova que a thread
                # tá viva e processando. Ausência disso por >60s = zumbi.
                job.heartbeat_em = datetime.now(timezone.utc)

                if job.iniciado_em is not None and job.duracao_estimada_s is not None:
                    elapsed = (
                        datetime.now(timezone.utc) - job.iniciado_em
                    ).total_seconds()
                    novo = progresso_estimado(elapsed, job.duracao_estimada_s)
                    # Nunca "volta" o progresso.
                    if novo > job.progresso_pct:
                        job.progresso_pct = novo
                db.commit()
        except Exception:
            # Thread de progresso é best-effort. Nunca deve derrubar o worker.
            log.exception("erro na thread de progresso do job %s", job_id)
        # 2s combina com o polling do frontend.
        stop_event.wait(2.0)


# -----------------------------------------------------------------------------
# Enfileirar / cancelar
# -----------------------------------------------------------------------------

def submeter(job_id: str, runner: Callable[[JobContext], None]) -> None:
    """
    Enfileira a execução do runner no pool. Se o pool estiver cheio, o
    ThreadPoolExecutor segura a tarefa até ter worker livre.

    O caller é responsável por ter CRIADO a linha de job antes (status=pendente),
    e por ter checado o limite de jobs por usuário.
    """
    if _runtime.pool is None:
        raise RuntimeError("executor de jobs não foi iniciado")
    _runtime.pool.submit(_executar_wrapper, job_id, runner)


def _executar_wrapper(job_id: str, runner: Callable[[JobContext], None]) -> None:
    """
    Wrapper que faz 3 coisas:
      1. marca job como `conectando` + iniciado_em
      2. sobe thread de progresso
      3. roda o runner — captura erro e marca status=erro se fugir
    """
    stop_event = threading.Event()
    try:
        # 1) Pré-execução: pode ter sido cancelado antes de rodar.
        with _sessao_thread() as db:
            job = db.get(JobExtracao, job_id)
            if job is None:
                return
            if job.status == STATUS_CANCELADO:
                return
            if job.status != STATUS_PENDENTE:
                # Alguma condição de corrida? Loga e segue.
                log.warning(
                    "job %s já não está pendente (status=%s); abortando",
                    job_id, job.status,
                )
                return
            job.status = STATUS_CONECTANDO
            job.iniciado_em = datetime.now(timezone.utc)
            db.commit()

        # 2) Thread de progresso (não precisa esperar por ela).
        with _runtime.lock:
            _runtime.progress_threads[job_id] = stop_event
        threading.Thread(
            target=_loop_progresso, args=(job_id, stop_event), daemon=True,
            name=f"job-progress-{job_id[:8]}",
        ).start()

        # 3) O runner cuida do resto.
        ctx = JobContext(job_id)
        try:
            runner(ctx)
        except Exception as e:
            log.exception("job %s falhou no runner", job_id)
            ctx.finalizar_erro(f"{type(e).__name__}: {e}")
    finally:
        # Garante que a thread de progresso para e sai do mapa.
        stop_event.set()
        with _runtime.lock:
            _runtime.progress_threads.pop(job_id, None)


def contar_jobs_ativos_do_usuario(db, usuario_id: int) -> int:
    """
    Conta jobs do usuário em estados ativos (pendente, conectando, etc).
    Usado no enqueue pra aplicar o limite.
    """
    return (
        db.query(JobExtracao)
        .filter(
            JobExtracao.usuario_id == usuario_id,
            JobExtracao.status.in_(STATUS_ATIVOS),
        )
        .count()
    )


def cancelar(db, job_id: str) -> bool:
    """
    Cancela um job pendente. Jobs que já começaram não são canceláveis
    (ThreadPoolExecutor não interrompe sem cooperação do worker, e matar
    uma query Oracle no meio do fetch pode deixar lixo). Retorna True se
    marcou como cancelado.
    """
    job = db.get(JobExtracao, job_id)
    if job is None:
        return False
    if job.status != STATUS_PENDENTE:
        return False
    job.status = STATUS_CANCELADO
    job.concluido_em = datetime.now(timezone.utc)
    db.commit()
    return True


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------

def caminho_do_csv(job_id: str) -> str:
    """Caminho absoluto onde o CSV do job deve ser escrito."""
    pasta = Path(get_settings().pasta_jobs)
    return str(pasta / f"{job_id}.csv")


def apagar_arquivo_do_job(job: JobExtracao) -> None:
    """Remove o CSV do disco se existir. Silencioso em erro."""
    if job.caminho_csv:
        try:
            os.remove(job.caminho_csv)
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("falha ao apagar CSV do job %s", job.id)
