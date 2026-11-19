# Jobs assíncronos — guia de infra e operação

A partir da Etapa 11 as extrações podem rodar em **background**: o usuário
dispara, recebe um `job_id`, acompanha o progresso e baixa o CSV quando
termina. Essa página documenta o que o SO precisa oferecer pra isso
funcionar em produção e como operar depois.

## Visão geral

```
POST /jobs/relatorios/{id}/extrair-async   → cria job (status=pendente)
                                             ↓
                          ThreadPool interno (2 workers)
                                             ↓
      status: pendente → conectando → consultando → tratando → escrevendo
                                             ↓
                        CSV em /var/lib/extrator/jobs/{id}.csv
                                             ↓
                                   status=concluido
                                             ↓
            GET /jobs/{id}/download → baixa; cron apaga depois de 1 dia
```

Tudo mora dentro do **mesmo processo FastAPI** — não tem serviço separado,
nem Redis, nem Celery. Isso basta até ~5 usuários simultâneos usando a
tela de jobs. Se um dia precisar escalar, o ponto de troca é só o
`app/jobs/executor.py`.

## Pré-requisitos no servidor

1. Pasta pros CSVs (gravável pelo usuário do uvicorn):

   ```bash
   sudo mkdir -p /var/lib/extrator/jobs
   sudo chown extrator:extrator /var/lib/extrator/jobs
   sudo chmod 750 /var/lib/extrator/jobs
   ```

   > **Atenção — hardening do systemd**: o unit `extrator-backend.service`
   > usa `ProtectSystem=strict`, que torna todo o filesystem read-only
   > exceto os paths listados em `ReadWritePaths=`. Precisa que
   > `/var/lib/extrator` esteja lá, ou o `to_csv()` quebra com
   > "Read-only file system". A versão desse repo já tem — se você tem
   > um `.service` antigo copiado, acrescente `/var/lib/extrator` na
   > linha e rode:
   >
   > ```bash
   > sudo systemctl daemon-reload
   > sudo systemctl restart extrator-backend
   > ```

2. Variáveis no `.env`:

   ```
   PASTA_JOBS=/var/lib/extrator/jobs
   JOBS_MAX_WORKERS=2
   JOBS_MAX_POR_USUARIO=1
   JOBS_RETENCAO_DIAS=1
   ```

3. Migration:

   ```bash
   cd /opt/extrator-protheus/backend
   sudo -u extrator .venv/bin/alembic upgrade head
   ```

4. Cronjob de limpeza (3 vezes por dia, cobre o caso "deixei rodando
   30 jobs à meia-noite"):

   ```bash
   sudo mkdir -p /var/log/extrator
   sudo chown extrator:extrator /var/log/extrator

   sudo tee /etc/cron.d/extrator-jobs > /dev/null <<'EOF'
   15 3,11,19 * * * extrator cd /opt/extrator-protheus/backend && \
       .venv/bin/python scripts/limpar_jobs.py \
       >> /var/log/extrator/limpar_jobs.log 2>&1
   EOF
   ```

   (O `extrator-deploy` do sudoers continua inalterado.)

5. Rotação do log (opcional mas recomendado):

   ```bash
   sudo tee /etc/logrotate.d/extrator > /dev/null <<'EOF'
   /var/log/extrator/*.log {
       weekly
       rotate 4
       compress
       missingok
       notifempty
       su extrator extrator
   }
   EOF
   ```

## O que o script de limpeza faz

- **Expira jobs antigos**: `concluido_em < agora - JOBS_RETENCAO_DIAS`,
  apagando o CSV + a linha.
- **Mata zumbis**: jobs ativos há mais de 4 horas (o processo caiu no meio)
  são marcados como `erro`, pra sair da fila do usuário.
- **Órfãos**: CSVs em `/var/lib/extrator/jobs/` sem job correspondente no
  banco são removidos.

Testar manualmente:

```bash
sudo -u extrator /opt/extrator-protheus/backend/.venv/bin/python \
    /opt/extrator-protheus/backend/scripts/limpar_jobs.py
```

## Watchdog de jobs zumbis

A partir da migration 0005, cada job tem a coluna `heartbeat_em`. A thread
de progresso (que já roda em paralelo ao job) atualiza esse campo a cada
2s. O serviço `extrator-scheduler` roda um loop a cada 60s e marca como
`erro` qualquer job em status ativo cujo heartbeat está parado há mais de
**2 minutos**.

Isso cobre o caso em que o worker do uvicorn morre em silêncio (segfault
em lib nativa, kill externo, OOM user-space) — antes dessa correção os
jobs ficavam "tratando 95%" eternamente, ou até a limpeza de 4h passar.

## Limites e trade-offs

- **1 job ativo por usuário, 2 em paralelo no total**. Protege o Oracle de
  consultas concorrentes pesadas e evita encher o disco. Configurável no
  `.env`.
- **Retenção 1 dia**. CSV sumiu? É re-rodar. Pensado pra disco pequeno; se
  for aumentar pra mais, lembre de monitorar o espaço.
- **Cancelar só funciona enquanto pendente**. Depois que entra em
  `conectando`, a thread não é interrompida — ThreadPoolExecutor não
  oferece kill cooperativo seguro, e matar uma query oracledb no meio do
  fetch pode deixar lixo. Para parar: reiniciar o serviço.
- **O processo caiu no meio do job**. A linha fica `conectando` até a
  próxima limpeza, que vira `erro`. O usuário vê o erro + motivo.
- **ETA honesto**. A barra chega até 95% baseado na mediana das últimas 10
  execuções bem-sucedidas desse mesmo relatório (logs_acesso). Quando o
  job realmente termina, pula pra 100%. Sem histórico → barra
  indeterminada.

## Endpoints

### POST /jobs/relatorios/{id}/extrair-async

Enfileira um relatório pronto. Payload = mesmo do síncrono.

```json
POST /jobs/relatorios/ct2010/extrair-async
{ "data_inicio": "2026-11-01", "data_fim": "2026-11-15" }

→ 200 { "job_id": "abc-uuid", "status": "pendente", "mensagem": "..." }
```

### POST /jobs/relatorio-livre/extrair-async

Mesmo payload do `/relatorio-livre/extrair`.

### POST /jobs/sql-livre/executar-async

```json
{ "sql": "SELECT ...", "nome_arquivo": "relatorio_x.csv" }
```

### GET /jobs

Lista os jobs do usuário (ordenados do mais recente ao mais antigo).
Admin pode passar `?todos=true` pra ver de todos os usuários.

### GET /jobs/{id}

Snapshot do job. Front faz polling nesse endpoint a cada 2s.

```json
{
  "id": "...",
  "status": "consultando",
  "progresso_pct": 42,
  "duracao_estimada_s": 180,
  "titulo": "CT2010 — 20261101 a 20261115",
  "iniciado_em": "2026-11-18T12:40:12Z",
  ...
}
```

### GET /jobs/{id}/download

CSV. 409 se o job ainda não concluiu, 410 se o arquivo expirou.

### DELETE /jobs/{id}

Cancela (só enquanto pendente).

## Códigos HTTP

- 403 → sem permissão pro relatório
- 404 → job inexistente ou de outro usuário
- 409 → tentativa de baixar antes de concluir, ou cancelar depois de começar
- 410 → CSV expirou (retenção)
- 429 → usuário já tem jobs demais ativos
