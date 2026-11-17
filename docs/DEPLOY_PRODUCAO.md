# Deploy em produção — passo a passo

Guia completo para colocar o Extrator Protheus em uma VM Ubuntu limpa.

Arquitetura:

```
Cliente (navegador)
        │
        ▼
Nginx :80 / :443 (TLS self-signed)
    ├─► /         →  frontend buildado (arquivos estáticos)
    └─► /api/*    →  uvicorn :8000  (unix com systemd, 4 workers)
                        ├─► PostgreSQL (loopback)
                        └─► Oracle Protheus (rede interna)
```

Cada seção abaixo é feita UMA VEZ, no setup inicial.
Pra atualizações depois, use `/opt/extrator-protheus/deploy/deploy.sh`.

---

## 1. Pré-requisitos no servidor

- Ubuntu Server 22.04+ (ou 24.04)
- VM com IP fixo na rede interna (no nosso caso: **192.168.3.128**)
- Acesso de rede ao Oracle Protheus (firewall liberado)
- Acesso SSH ou console pra rodar os comandos abaixo

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    nginx \
    git curl build-essential libpq-dev \
    openssl

# Node.js 20+ (NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Confira as versões
python3 --version    # 3.10+
node --version       # 20.x
psql --version       # 14+
nginx -v
```

---

## 2. Usuário dedicado pra rodar o app

Rodar app como `root` é péssima prática. Criamos um usuário sem shell de
login, dono dos arquivos do projeto:

```bash
sudo useradd --system --home-dir /opt/extrator-protheus --shell /usr/sbin/nologin extrator
```

---

## 3. PostgreSQL — banco e usuário

Como `postgres`:

```bash
sudo -u postgres psql
```

No prompt do psql:

```sql
CREATE USER extrator WITH PASSWORD 'ESCOLHA_UMA_SENHA_FORTE_AQUI';
CREATE DATABASE extrator OWNER extrator;
GRANT ALL PRIVILEGES ON DATABASE extrator TO extrator;
\q
```

Testar conexão:

```bash
psql -h localhost -U extrator -d extrator
# Se o prompt abrir: OK. Se pedir senha e der erro, ajuste pg_hba.conf
# pra permitir 'scram-sha-256' em local, e reinicie:
#   sudo systemctl restart postgresql
```

---

## 4. Clonar o projeto

O `extrator` não tem shell, então clonamos como `root` e depois
transferimos a posse:

```bash
sudo mkdir -p /opt/extrator-protheus
sudo chown $USER:$USER /opt/extrator-protheus
cd /opt
# Troque a URL pelo seu repositório GitHub
git clone https://github.com/montenegro-dev-ti/extrator-protheus-web.git extrator-protheus
cd extrator-protheus

# Transfere a posse pro usuário extrator (incluindo .git/)
sudo chown -R extrator:extrator /opt/extrator-protheus
```

---

## 5. Backend — venv, dependências, migrations

Como `root` (sudo -u extrator pra executar como o usuário certo):

```bash
cd /opt/extrator-protheus/backend

# Cria venv
sudo -u extrator python3 -m venv .venv

# Deps
sudo -u extrator ./.venv/bin/pip install --upgrade pip
sudo -u extrator ./.venv/bin/pip install -r requirements.txt

# .env de produção
sudo -u extrator cp .env.production.example .env
# Preencha todos os valores:
sudo nano /opt/extrator-protheus/backend/.env
```

No `.env`, substitua:

- `POSTGRES_URL` — com a senha do passo 3
- `ORACLE_*` — credenciais Oracle
- `SECRET_KEY` — gerar nova (importante: NÃO reusar a de dev):
  ```bash
  sudo -u extrator ./.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- `PASTA_APOIO` — `/opt/extrator-protheus/tb_APOIO` (veja passo 6)

Permissões do `.env` (nunca legível pelos outros):

```bash
sudo chmod 600 /opt/extrator-protheus/backend/.env
sudo chown extrator:extrator /opt/extrator-protheus/backend/.env
```

Rodar migrations:

```bash
cd /opt/extrator-protheus/backend
sudo -u extrator ./.venv/bin/alembic upgrade head
```

Criar o primeiro admin:

```bash
sudo -u extrator ./.venv/bin/python scripts/criar_admin.py
```

---

## 6. Planilhas de apoio (tb_APOIO)

O CT2010 usa duas planilhas (Plano de Contas + Centro de Custo). Suba via
SCP/WinSCP ou crie a pasta e copie manualmente:

```bash
sudo mkdir -p /opt/extrator-protheus/tb_APOIO
# Copie os .xlsx pra essa pasta
# Depois:
sudo chown -R extrator:extrator /opt/extrator-protheus/tb_APOIO
sudo chmod -R 640 /opt/extrator-protheus/tb_APOIO/*.xlsx
```

---

## 7. Certificado HTTPS self-signed

Vamos gerar um certificado válido por 10 anos pro IP 192.168.3.128.
Os navegadores vão reclamar na primeira visita ("conexão não privada"),
você clica **Avançado → Prosseguir** uma vez e ele lembra.

```bash
sudo mkdir -p /etc/ssl/extrator

# Config de certificado com SAN pro IP (navegadores modernos exigem SAN).
sudo tee /etc/ssl/extrator/openssl.cnf > /dev/null <<'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C  = BR
ST = PR
L  = Curitiba
O  = Technocoat
CN = 192.168.3.128

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment

[alt_names]
IP.1 = 192.168.3.128
DNS.1 = extrator.local
EOF

# Gera a chave e o certificado (10 anos).
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/ssl/extrator/privkey.pem \
    -out    /etc/ssl/extrator/fullchain.pem \
    -config /etc/ssl/extrator/openssl.cnf \
    -extensions v3_req

# Trava permissões (chave privada só pra root).
sudo chmod 600 /etc/ssl/extrator/privkey.pem
sudo chmod 644 /etc/ssl/extrator/fullchain.pem
```

Quando trocar pra DNS (futuro `extrator.technocoat.local`), basta gerar
outro certificado trocando o `CN` e adicionando o DNS no SAN.

---

## 8. Frontend — build de produção

```bash
cd /opt/extrator-protheus/frontend
sudo -u extrator npm ci --no-audit --no-fund
sudo -u extrator npm run build
# Gera /opt/extrator-protheus/frontend/dist/
```

Se der erro de permissão no npm:

```bash
sudo chown -R extrator:extrator /opt/extrator-protheus/frontend
```

---

## 9. systemd — instalar o serviço do backend

```bash
sudo cp /opt/extrator-protheus/deploy/extrator-backend.service \
    /etc/systemd/system/extrator-backend.service

sudo systemctl daemon-reload
sudo systemctl enable extrator-backend
sudo systemctl start extrator-backend

# Verificar que subiu OK
sudo systemctl status extrator-backend
# Logs em tempo real (Ctrl+C sai):
sudo journalctl -u extrator-backend -f
```

Deve aparecer algo como `Uvicorn running on http://127.0.0.1:8000`.

Teste rápido do backend via loopback:

```bash
curl http://127.0.0.1:8000/health
# Deve retornar o JSON do health check
```

---

## 10. Nginx — reverse proxy

```bash
# Instala o config
sudo cp /opt/extrator-protheus/deploy/nginx-extrator.conf \
    /etc/nginx/sites-available/extrator

# Habilita o site (link simbólico)
sudo ln -s /etc/nginx/sites-available/extrator /etc/nginx/sites-enabled/

# Desabilita o site default (opcional, mas recomendado)
sudo rm -f /etc/nginx/sites-enabled/default

# Testa a config antes de aplicar
sudo nginx -t

# Aplica
sudo systemctl reload nginx
```

---

## 11. Firewall (opcional mas recomendado)

Se `ufw` estiver instalado:

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (só redireciona)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

---

## 12. Teste final

Abra no navegador de qualquer máquina da rede interna:

```
https://192.168.3.128/
```

- Primeiro acesso: aviso de certificado. Avançado → Prosseguir. Só uma vez.
- Tela de login aparece
- Logue com o admin criado no passo 5
- Teste um relatório pra ponta a ponta

---

## Atualizações futuras

A cada push na branch `main`:

```bash
cd /opt/extrator-protheus
sudo -u extrator ./deploy/deploy.sh
```

O script:
1. `git pull` da origin/main
2. Atualiza deps do backend
3. Roda migrations pendentes
4. Rebuilda o frontend
5. Restart do backend + reload do Nginx

---

## Troubleshooting

### Backend não sobe

```bash
sudo journalctl -u extrator-backend -n 50 --no-pager
```

Erros comuns:
- `could not connect to Postgres` → confira `POSTGRES_URL` no `.env`
- `cannot connect to Oracle` → firewall/VPN; teste `nc -zv ORACLE_HOST 1521`
- `ModuleNotFoundError` → venv desatualizada; rode `pip install -r requirements.txt`

### Nginx retorna 502 Bad Gateway

Backend caiu. Confira `systemctl status extrator-backend`.

### Login funciona mas é logout imediato

Cookie `secure=true` exige HTTPS. Se estiver testando via HTTP, troque
temporariamente `ENV=development` no `.env` ou acesse via `https://`.

### "Mixed content" no console do navegador

Alguma chamada tá indo pra HTTP enquanto a página é HTTPS. Confira se o
proxy do Vite não tá habilitado em prod (em prod o Nginx faz o proxy;
o Vite não é usado).

### Certificado expirou

```bash
# Gere um novo com o mesmo comando do passo 7
sudo systemctl reload nginx
```

### Ver logs de acesso

```bash
sudo tail -f /var/log/nginx/extrator-access.log
sudo journalctl -u extrator-backend -f
```

### Dar rollback de uma versão

```bash
cd /opt/extrator-protheus
sudo -u extrator git log --oneline -20          # lista commits
sudo -u extrator git reset --hard <COMMIT_ANTIGO>
sudo -u extrator ./deploy/deploy.sh             # rebuild e reload
```

Atenção com migrations do Alembic — rollback de código que remove uma
migration precisa de `alembic downgrade` manual antes do deploy.

---

## Backup do PostgreSQL

Diário, via cron:

```bash
sudo mkdir -p /var/backups/extrator
sudo chown postgres:postgres /var/backups/extrator

# Adicione no crontab do postgres:
sudo crontab -u postgres -e
```

Adicionar:

```
# Backup diário às 02:00, mantém 14 dias
0 2 * * * pg_dump extrator | gzip > /var/backups/extrator/extrator-$(date +\%Y\%m\%d).sql.gz
0 3 * * * find /var/backups/extrator -name "extrator-*.sql.gz" -mtime +14 -delete
```

Restore (em caso de emergência):

```bash
sudo -u postgres dropdb extrator
sudo -u postgres createdb extrator -O extrator
gunzip -c /var/backups/extrator/extrator-20261116.sql.gz | sudo -u postgres psql extrator
```
