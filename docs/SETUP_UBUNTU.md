# Setup — VM Ubuntu

Passo a passo para subir o projeto do zero numa VM Ubuntu (a mesma onde
está o PostgreSQL).

## Pré-requisitos

- Ubuntu 22.04+ (ou 24.04)
- PostgreSQL já instalado e rodando
- Acesso de rede ao Oracle Protheus
- `sudo` disponível

## 1. Instalar dependências do sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl build-essential libpq-dev

# Node.js 20+ (para o frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

node --version    # deve mostrar 20.x
python3 --version # deve mostrar 3.10+
```

## 2. Preparar o PostgreSQL

Criar banco e usuário dedicados para o app. Como postgres (`sudo -u postgres psql`):

```sql
CREATE USER extrator WITH PASSWORD 'troque_esta_senha';
CREATE DATABASE extrator OWNER extrator;
GRANT ALL PRIVILEGES ON DATABASE extrator TO extrator;
```

Sair do psql (`\q`) e testar login:

```bash
psql -h localhost -U extrator -d extrator
# vai pedir a senha; se abrir o prompt do psql, está OK
```

Se der erro de autenticação, ajustar `/etc/postgresql/<versao>/main/pg_hba.conf`
para permitir `md5` ou `scram-sha-256` em conexões locais e reiniciar:
`sudo systemctl restart postgresql`.

## 3. Clonar o projeto

```bash
cd /opt
sudo mkdir extrator-protheus
sudo chown $USER:$USER extrator-protheus
cd extrator-protheus
# copiar ou clonar o projeto para esta pasta
```

## 4. Backend — virtualenv + dependências

```bash
cd /opt/extrator-protheus/backend

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Criar o `.env` a partir do exemplo:

```bash
cp .env.example .env
nano .env
```

Preencher pelo menos:

- `POSTGRES_URL` — com a senha que você definiu no passo 2
- `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, `ORACLE_PASSWORD`
- `SECRET_KEY` — gerar com:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

## 5. Rodar as migrations

Com a venv ainda ativa, do diretório `backend/`:

```bash
alembic upgrade head
```

Deve criar as 4 tabelas: `usuarios`, `permissoes_relatorio`, `logs_acesso`,
`sessoes`. Para conferir:

```bash
psql -h localhost -U extrator -d extrator -c "\dt"
```

## 6. Subir o backend em modo dev

```bash
cd /opt/extrator-protheus/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Em outra janela, testar:

```bash
curl http://localhost:8000/health
```

Resposta esperada (algo como):

```json
{
  "ok": true,
  "ambiente": "development",
  "postgres": {"ok": true, "detalhe": "conectado"},
  "oracle":   {"ok": true, "detalhe": "conectado"}
}
```

## 7. Frontend — instalar e rodar

Em outra janela/aba de terminal:

```bash
cd /opt/extrator-protheus/frontend
npm install
npm run dev -- --host 0.0.0.0
```

Abrir no navegador (se estiver acessando a VM pela rede, trocar `localhost`
pelo IP da VM):

- http://localhost:5173

A tela deve mostrar os três serviços verdes.

## 8. (Opcional) Deploy como serviço systemd — Etapa futura

Quando a etapa de deploy chegar, criamos `/etc/systemd/system/extrator.service`
e um Nginx na frente para HTTPS. Por enquanto, rodar em dev é suficiente.
