# Agendamentos — infra e operação

A partir da Etapa 14 um usuário pode agendar relatórios pra rodarem
automaticamente em horários recorrentes. O resultado fica disponível tanto
na tela `/agendamentos` quanto num **script sincronizador** que o usuário
instala no PC pra baixar os CSVs direto numa pasta local (ex: OneDrive).

## Arquitetura

```
┌────────────── VM ──────────────────────────────────────────┐
│                                                            │
│  systemd: extrator-scheduler.service                       │
│    loop 60s → acorda agendamentos vencidos                 │
│    dispatcher: resolve preset de datas, cria JobExtracao   │
│                                                            │
│  systemd: extrator-backend.service (uvicorn)               │
│    executor de jobs (mesmo da Etapa 11)                    │
│    endpoints /agendamentos/*                               │
│                                                            │
│  /var/lib/extrator/jobs/ ← CSV do agendamento (7 dias)     │
└──────────────────────────────┬─────────────────────────────┘
                               │ GET /agendamentos/{id}/execucoes/pendentes
                               │ POST /agendamentos/{id}/execucoes/{e}/baixada
         ┌─────────────────────┴────────────────────────┐
         │   PC do usuário                              │
         │   extrator-sync-<id>.py                      │
         │   (Task Scheduler: 1x/hora + no login)       │
         │   → salva CSV em C:\...\OneDrive\...          │
         └──────────────────────────────────────────────┘
```

## Pré-requisitos no servidor

1. **Pasta `/var/lib/extrator/jobs`** já existe (criada na Etapa 11). O
   scheduler usa a mesma. Se ainda não criou:

   ```bash
   sudo mkdir -p /var/lib/extrator/jobs
   sudo chown extrator:extrator /var/lib/extrator/jobs
   sudo chmod 750 /var/lib/extrator/jobs
   ```

2. **Nova variável no `.env`** — `API_BASE_EXTERNA`. É o endereço que o script
   vai bater. Precisa ser **o endereço que o PC do usuário consegue alcançar**
   (não `localhost`).

   ```
   API_BASE_EXTERNA=http://192.168.3.128
   ```

   Se for HTTPS por trás do Nginx: `https://extrator.technocoat.local`.

3. **Migration 0004**:

   ```bash
   cd /opt/extrator-protheus/backend
   sudo -u extrator .venv/bin/alembic upgrade head
   ```

4. **Novo serviço systemd `extrator-scheduler`**:

   ```bash
   sudo cp deploy/extrator-scheduler.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now extrator-scheduler
   sudo systemctl status extrator-scheduler
   ```

   Pra ver logs:

   ```bash
   journalctl -u extrator-scheduler -f
   ```

5. **Reiniciar o backend** pra carregar o novo router:

   ```bash
   sudo systemctl restart extrator-backend
   ```

## Como funciona o dispatch

A cada 60 segundos o scheduler:

1. Bootstrap de `proxima_execucao` em agendamentos ativos novos (NULL).
2. Busca agendamentos ativos com `proxima_execucao <= now()`.
3. Pra cada um:
   - Rechecar se o usuário está ativo e ainda tem permissão no relatório
     (se não: **pausa** o agendamento com motivo registrado numa execução
     de erro).
   - Resolve o preset de datas (`ontem`, `últimos_7`, `mês_anterior`…).
   - Cria um `JobExtracao` (reusa a infra da Etapa 11).
   - Cria uma linha `AgendamentoExecucao` (status=`pendente`) vinculada.
   - Atualiza `ultima_execucao` e recalcula `proxima_execucao`.
4. Sincroniza execuções `pendente` cujo job já terminou → vira `concluida`
   ou `erro`.

## Tokens

Cada agendamento tem um **API token** único (formato
`sk_ag_<id>_<rand>`). O token em claro aparece **uma única vez** na tela
após a criação (ou regeneração). O banco guarda só o bcrypt.

O script embute esse token. Se o usuário perder: regenera na UI (o script
antigo para de funcionar imediatamente).

## Retenção

- CSV do agendamento: **7 dias** no servidor (default). O script `limpar_jobs.py`
  da Etapa 11 continua o único responsável pela limpeza do disco; jobs
  vinculados a agendamento seguem a retenção do próprio job
  (`JOBS_RETENCAO_DIAS` no `.env`, default 1 dia).

> **Ajuste pendente**: idealmente o cleanup de jobs considera a
> `retencao_dias` do agendamento quando o job veio de um. Por ora, vale
> aumentar o `JOBS_RETENCAO_DIAS` pra 7 se for agendar bastante — o custo
> é só disco.

## Endpoints

### CRUD (UI, cookie de sessão)

| Método | Caminho | Finalidade |
|---|---|---|
| GET | `/agendamentos` | Lista os do usuário (admin vê todos) |
| POST | `/agendamentos` | Cria. Response inclui `token_claro` (único momento) |
| PATCH | `/agendamentos/{id}` | Edita; recalcula `proxima_execucao` |
| DELETE | `/agendamentos/{id}` | Apaga + cascata nas execuções |
| POST | `/agendamentos/{id}/regenerar-token` | Novo token (invalida o anterior) |
| POST | `/agendamentos/{id}/testar` | Dispara agora, sem alterar cronograma |
| GET | `/agendamentos/{id}/execucoes` | Histórico |
| GET | `/agendamentos/{id}/execucoes/{e}/download` | Baixa CSV manualmente |
| POST | `/agendamentos/{id}/script?so=windows` | Gera o script (requer header `X-Token-Claro`) |

### Script (header `X-Agendamento-Token`)

| Método | Caminho | Finalidade |
|---|---|---|
| GET | `/agendamentos/{id}/execucoes/pendentes?maquina_id=X` | Execuções ainda não baixadas por essa máquina |
| GET | `/agendamentos/{id}/execucoes/{e}/download-script` | Baixa CSV |
| POST | `/agendamentos/{id}/execucoes/{e}/baixada` | Callback de sucesso/erro + id da máquina |

## Diagnóstico

- **Scheduler não dispara nada**: `systemctl status extrator-scheduler` +
  `journalctl -u extrator-scheduler -n 50`. Verifica se `proxima_execucao`
  no banco está no passado; se não, é o cálculo que está errado (checar TZ).
- **Script dá 401**: token inválido ou agendamento desativado.
- **Script baixa mas o PC do usuário não enxerga a API**: `API_BASE_EXTERNA`
  no `.env` aponta pra um endereço só visível internamente. Precisa ser o
  endereço da rede/VPN.
