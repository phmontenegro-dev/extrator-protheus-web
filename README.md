# Extrator Protheus — Web

Ferramenta web interna para extrair relatórios do ERP Protheus (Totvs/Oracle),
com controle de acesso, auditoria de uso e gestão de usuários/permissões.

Substitui a versão desktop ([ExtratorProtheus](https://github.com/)), que não
funciona fora da rede corporativa por causa do bloqueio de IP no Oracle.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Alembic + oracledb + pandas
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Banco interno**: PostgreSQL (usuários, permissões, logs, sessões)
- **ERP**: Oracle Protheus (somente leitura)
- **Auth**: cookie httpOnly com token de sessão de 8 horas (rolling)

## Features

- Autenticação com rate-limit (5 falhas / 15 min por IP)
- Painel administrativo (gestão de usuários, permissões por relatório, auditoria)
- 10 relatórios prontos com regras de negócio específicas (CT2010, QPR010, SFT010, SD3010, família SUZANO)
- Relatório Livre: extração crua de qualquer tabela Protheus com validação dinâmica de colunas
- Logs de auditoria granulares (quem rodou o quê, quando, com quais filtros, em quanto tempo)
- Download de CSV direto do navegador (UTF-8 com BOM, pronto pra abrir no Excel)

## Estrutura

```
ExtratorProtheusWeb/
├── backend/                                   FastAPI
│   ├── app/
│   │   ├── main.py                            entrada
│   │   ├── config.py                          Settings (.env)
│   │   ├── database.py                        SQLAlchemy — Postgres
│   │   ├── oracle.py                          conexão Protheus (call_timeout 10 min)
│   │   ├── auth/                              login, sessão, rate limit
│   │   ├── models/                            Usuario, Permissao, LogAcesso, Sessao
│   │   ├── schemas/                           Pydantic (request/response)
│   │   ├── routers/                           health, auth, relatorios, relatorio_livre, admin
│   │   ├── relatorios_prontos/                um pacote por relatório (extrair + tratar)
│   │   ├── relatorio_livre/                   consulta dinâmica + extração
│   │   └── utils/                             logs, permissões, csv runner
│   ├── alembic/                               migrations versionadas
│   ├── scripts/
│   │   └── criar_admin.py                     CLI pra primeiro admin
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                                  React + Vite + TS + Tailwind
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                            roteador + guards
│   │   ├── api/                               axios wrappers tipados
│   │   ├── auth/                              AuthContext + RequireAuth + RequireAdmin
│   │   └── pages/
│   │       ├── Login.tsx
│   │       ├── Menu.tsx
│   │       ├── admin/                         painel + usuários + logs
│   │       └── relatorios/
│   │           ├── RelatorioGenerico.tsx      dispatcher pro form certo
│   │           └── FormLivre.tsx              UI do Relatório Livre
│   ├── package.json
│   ├── vite.config.ts                         proxy /api → :8000
│   └── tailwind.config.js
│
└── docs/
    └── SETUP_UBUNTU.md                        passo a passo de instalação
```

## Setup rápido (dev)

### Pré-requisitos

- Ubuntu 22.04+ (ou outra distro Linux)
- PostgreSQL 14+ rodando localmente
- Python 3.10+ e Node.js 20+
- Acesso de rede ao Oracle Protheus (IP liberado no firewall)

### Passo a passo

Veja o guia completo em [docs/SETUP_UBUNTU.md](docs/SETUP_UBUNTU.md).

## Documentação técnica

- [Setup em Ubuntu (dev)](docs/SETUP_UBUNTU.md)
- [Deploy em produção](docs/DEPLOY_PRODUCAO.md) · [Passo a passo iniciante](docs/DEPLOY_PASSO_A_PASSO.md)
- [**Como adicionar um novo relatório pronto**](docs/COMO_ADICIONAR_RELATORIO.md) ← consulta durante o desenvolvimento

Resumo:

```bash
# 1) Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite .env com as credenciais do Oracle e do Postgres
alembic upgrade head
python scripts/criar_admin.py           # cria o primeiro usuário admin

# 2) Frontend (em outro terminal)
cd frontend
npm install
cp .env.example .env                    # se existir; senão opcional

# 3) Rodar em dev
# terminal backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# terminal frontend
cd frontend
npm run dev -- --host 0.0.0.0
```

Acessar `http://localhost:5173` e logar com o admin criado.

## Variáveis de ambiente

Veja `backend/.env.example` para a lista completa. As principais:

| Variável | Descrição |
|---|---|
| `POSTGRES_URL` | Conexão com o banco interno (ex.: `postgresql+psycopg://user:pwd@localhost/extrator`) |
| `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE` | Oracle Protheus |
| `ORACLE_USER`, `ORACLE_PASSWORD` | Credenciais Oracle (idealmente usuário com SELECT only) |
| `SECRET_KEY` | Chave de 48+ bytes para assinar cookies (gerar com `python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `CORS_ORIGINS` | Em dev, `http://localhost:5173`. Em produção, vazio (FastAPI serve o frontend) |
| `PASTA_APOIO` | Caminho pras planilhas de PROCV do CT2010 |
| `ORACLE_QUERY_TIMEOUT_S` | Timeout das queries Oracle (default 600s) |

## Segurança

- Todas as senhas armazenadas com bcrypt (passlib)
- Cookies de sessão httpOnly + SameSite=Lax, com `secure=true` em produção
- Rate limit de login: 5 tentativas em 15 min por IP
- Mensagem genérica de "usuário ou senha inválidos" (não revela se o usuário existe)
- Admin não pode se auto-desativar; último admin ativo não pode ser despromovido
- Relatório Livre: defesa em profundidade na montagem do SQL (tabela/colunas validadas contra o dicionário Oracle antes de interpolar)
- `.env` real nunca versionado — apenas `.env.example`
- Logs de auditoria completos (todo login, logout, extração, mudança admin)

## Roadmap

- [x] Esqueleto + health check
- [x] Autenticação ponta a ponta
- [x] Primeiro relatório funcionando (CT2010)
- [x] Painel admin (usuários, permissões, logs)
- [x] 10 relatórios prontos migrados
- [x] Relatório Livre
- [x] **Deploy em produção** — ver [docs/DEPLOY_PRODUCAO.md](docs/DEPLOY_PRODUCAO.md)
- [ ] Melhorias visuais e personalização
- [ ] Divisão de relatórios por área (ex: Contábil, Qualidade, Estoque,
      Produção, Suzano) — menu agrupado por área, admin cadastra/edita áreas
- [ ] Tela "Código SQL" (consulta livre, para admins)
- [ ] Extração assíncrona (job em background + barra de progresso)
- [ ] Filtros dinâmicos no Relatório Livre (operadores por tipo de coluna:
      `=`, `>`, `<`, `LIKE`, `BETWEEN`, `IN`) além do filtro de data
- [ ] Dashboards com gráficos de relatórios pré-definidos (visões analíticas
      configuráveis, ex: custos, produção, saldo de estoque)

## Autor

Pedro Henrique Ceschin Montenegro — Analista de TI na Technocoat (Curitiba, PR).
