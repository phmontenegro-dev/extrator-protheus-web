# Deploy em produção — passo a passo nível iniciante

Este guia assume **ZERO conhecimento prévio** de servidor Linux. Siga na ordem.

**Antes de começar**, você precisa de:

- A VM Ubuntu rodando no Proxmox, com IP **192.168.3.128**
- Um usuário no servidor com `sudo` (vou chamar de "você" no guia)
- Acesso SSH funcionando (`ssh seu_usuario@192.168.3.128`)
- Seu projeto já no GitHub (pode ser privado) — vou chamar de
  `https://github.com/SEU-USUARIO/extrator-protheus-web.git`
- As planilhas `2 - Plano de Contas.xlsx` e `3 - Centro de Custo.xlsx` prontas
  no seu PC pra enviar depois

Convenções deste guia:

- Linha começando com `$` → cole no terminal (**sem** o `$`)
- Linha começando com `✅` → o que você DEVERIA ver se deu certo
- Linha começando com `❌` → o que significa quando dá erro, e como arrumar

---

## PARTE 1 — Preparar o servidor (uma vez só)

### 1.1 Conectar na VM

No PowerShell do seu PC Windows:

```
$ ssh seu_usuario@192.168.3.128
```

Se for a primeira vez, vai perguntar se confia na máquina. Responda `yes`.
Depois digita a senha do seu usuário Linux.

✅ Agora você tá "dentro" da VM. O prompt muda pra algo como
`seu_usuario@vm-extrator:~$`.

### 1.2 Atualizar o sistema

```
$ sudo apt update && sudo apt upgrade -y
```

Vai demorar 1-5 minutos. Se perguntar algo sobre "manter config atual", pode
aceitar (geralmente é tecla `Enter`).

### 1.3 Instalar tudo que o projeto precisa

**UM comando só**, cola tudo de uma vez:

```
$ sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib nginx git curl build-essential libpq-dev openssl
```

Depois instala o Node.js 20:

```
$ curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
$ sudo apt install -y nodejs
```

Confere que tudo instalou:

```
$ python3 --version
$ node --version
$ psql --version
$ nginx -v
```

✅ Você deveria ver:
- Python 3.10 (ou mais novo)
- v20.x.x
- psql (PostgreSQL) 14 (ou mais novo)
- nginx version: nginx/1.x.x

---

## PARTE 2 — Preparar o PostgreSQL

### 2.1 Entrar no Postgres

```
$ sudo -u postgres psql
```

✅ O prompt muda pra `postgres=#`. Você tá "dentro" do Postgres agora.

### 2.2 Criar banco e usuário

**IMPORTANTE**: Escolha uma senha forte pra trocar onde diz
`SUA_SENHA_POSTGRES_AQUI`. **ANOTE essa senha** — vai precisar daqui a pouco.

Cola as 3 linhas (uma de cada vez ou todas juntas):

```
CREATE USER extrator WITH PASSWORD 'SUA_SENHA_POSTGRES_AQUI';
CREATE DATABASE extrator OWNER extrator;
GRANT ALL PRIVILEGES ON DATABASE extrator TO extrator;
```

✅ Depois de cada comando aparece `CREATE ROLE`, `CREATE DATABASE`, `GRANT`.

Sai do Postgres:

```
\q
```

### 2.3 Testar que a senha funciona

```
$ psql -h localhost -U extrator -d extrator
```

Vai pedir a senha. Cola a que você escolheu.

✅ Prompt muda pra `extrator=>`. Deu certo. Sai com `\q`.

❌ Se der "password authentication failed" — a senha tá errada ou o
pg_hba.conf precisa ajuste. Me chama que resolvo esse caso específico.

---

## PARTE 3 — Criar o usuário Linux que vai rodar o app

Boas práticas: o app não roda como `root` nem como você. Tem um usuário
dedicado chamado `extrator`.

```
$ sudo useradd --system --home-dir /opt/extrator-protheus --shell /usr/sbin/nologin extrator
```

✅ Não dá output nenhum. Tá certo. Esse usuário não tem shell — ninguém
consegue "logar" como ele, só processos de sistema usam.

---

## PARTE 4 — Baixar o código do GitHub

### 4.1 Preparar a pasta

```
$ sudo mkdir -p /opt/extrator-protheus
$ sudo chown $USER:$USER /opt/extrator-protheus
```

### 4.2 Clonar o repositório

**Troque `SEU-USUARIO` pelo seu usuário real do GitHub** e o nome do repo:

```
$ cd /opt
$ git clone https://github.com/SEU-USUARIO/extrator-protheus-web.git extrator-protheus
```

Se for repositório **privado**, vai pedir usuário e senha:
- **Username**: seu usuário do GitHub
- **Password**: o **PAT** (Personal Access Token) que a gente criou antes.
  NÃO é a senha do GitHub.

✅ Baixa os arquivos. Deve mostrar `Receiving objects: 100%...`

### 4.3 Transferir posse pro usuário `extrator`

```
$ sudo chown -R extrator:extrator /opt/extrator-protheus
```

Daqui pra frente, tudo que for comando dentro de `/opt/extrator-protheus/`
roda com `sudo -u extrator` na frente, porque o dono dos arquivos é ele.

---

## PARTE 5 — Configurar o backend

### 5.1 Entrar na pasta do backend

```
$ cd /opt/extrator-protheus/backend
```

### 5.2 Criar o "ambiente virtual" Python (venv)

Venv é uma caixinha isolada com as libs do projeto, pra não bagunçar o
Python do sistema.

```
$ sudo -u extrator python3 -m venv .venv
```

✅ Cria uma pasta `.venv/` com um Python dedicado. Sem output.

### 5.3 Instalar as dependências do Python

```
$ sudo -u extrator ./.venv/bin/pip install --upgrade pip
$ sudo -u extrator ./.venv/bin/pip install -r requirements.txt
```

Demora 1-3 minutos. Vai aparecer muita linha de "Collecting...",
"Downloading...". No fim:

✅ `Successfully installed ...` (lista enorme de pacotes)

### 5.4 Criar o arquivo .env com as senhas

**Esse é o passo mais importante.** Vamos copiar o template e preencher.

```
$ sudo -u extrator cp .env.production.example .env
$ sudo nano /opt/extrator-protheus/backend/.env
```

O editor `nano` abre dentro do terminal. Vai aparecer o arquivo com valores
de placeholder. **Você precisa editar TODAS essas linhas**:

- `POSTGRES_URL=...` → substitui `senha_real` pela senha do passo 2.2
- `ORACLE_HOST=...` → IP do Oracle Protheus
- `ORACLE_PORT=1521` → geralmente 1521
- `ORACLE_SERVICE=...` → nome do service Oracle
- `ORACLE_USER=...` e `ORACLE_PASSWORD=...` → credenciais Oracle
- `SECRET_KEY=TROQUE_...` → vamos gerar uma nova agora. Veja abaixo.
- `PASTA_APOIO=/opt/extrator-protheus/tb_APOIO` → esse já tá certo

**Pra gerar a SECRET_KEY**: abre OUTRO terminal SSH (conecta de novo em
outra janela), roda:

```
$ sudo -u extrator /opt/extrator-protheus/backend/.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Vai cuspir uma string grande tipo
`xZ8kL2aP9mN3qR5tV6wY7cE1dF4gH0iJ2kL3mN4oP5qR6sT7uV8wX9yZ`. **Copia essa string**
e cola no `.env` depois de `SECRET_KEY=`.

**Pra salvar no nano**: `Ctrl+O` → `Enter` (confirma nome) → `Ctrl+X` (sai).

### 5.5 Travar as permissões do .env

Esse arquivo tem senhas. Ninguém além do `extrator` pode ler.

```
$ sudo chmod 600 /opt/extrator-protheus/backend/.env
$ sudo chown extrator:extrator /opt/extrator-protheus/backend/.env
```

### 5.6 Criar as tabelas do banco (migrations)

```
$ cd /opt/extrator-protheus/backend
$ sudo -u extrator ./.venv/bin/alembic upgrade head
```

✅ Aparece algo como `Running upgrade -> 0001_initial, initial — usuarios...`

❌ Se der erro de conexão com Postgres: senha errada no `.env`. Volta no
passo 5.4 e confere.

### 5.7 Criar o primeiro usuário admin

```
$ sudo -u extrator ./.venv/bin/python scripts/criar_admin.py
```

Vai perguntar interativamente:
- **Username**: seu nome (ex: `pedro`)
- **Nome completo**: Pedro Henrique Ceschin Montenegro
- **Email**: `montenegro.dev.ti@gmail.com` (opcional, pode pular com Enter)
- **Senha**: senha com pelo menos 8 caracteres + 1 especial (ex: `Technocoat@2026`)
- **Confirme a senha**: digita de novo

✅ "Usuário admin 'pedro' criado com sucesso."

---

## PARTE 6 — Enviar as planilhas de apoio

Essas planilhas não vão no GitHub (contêm dados da empresa), então sobe
manualmente.

### 6.1 Criar a pasta

```
$ sudo mkdir -p /opt/extrator-protheus/tb_APOIO
```

### 6.2 Subir os arquivos do seu PC Windows

Abre o **PowerShell** DO SEU PC (NÃO SSH, PowerShell local), na pasta onde
estão os xlsx:

```
> scp "2 - Plano de Contas.xlsx" "3 - Centro de Custo.xlsx" seu_usuario@192.168.3.128:/tmp/
```

Vai pedir senha. Copia os arquivos pra `/tmp/` da VM.

### 6.3 Mover pra pasta certa e ajustar permissões

De volta no SSH da VM:

```
$ sudo mv "/tmp/2 - Plano de Contas.xlsx" /opt/extrator-protheus/tb_APOIO/
$ sudo mv "/tmp/3 - Centro de Custo.xlsx" /opt/extrator-protheus/tb_APOIO/
$ sudo chown -R extrator:extrator /opt/extrator-protheus/tb_APOIO
```

Confirma que tá lá:

```
$ ls -la /opt/extrator-protheus/tb_APOIO/
```

✅ Deve mostrar os dois .xlsx pertencendo ao usuário `extrator`.

---

## PARTE 7 — Gerar o certificado HTTPS

Isso é o que faz o navegador abrir `https://` em vez de `http://`.

### 7.1 Criar a pasta pros arquivos de certificado

```
$ sudo mkdir -p /etc/ssl/extrator
```

### 7.2 Criar o arquivo de configuração

```
$ sudo nano /etc/ssl/extrator/openssl.cnf
```

Dentro do nano, cola **exatamente** isso:

```
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
```

Salva: `Ctrl+O` → `Enter` → `Ctrl+X`.

### 7.3 Gerar certificado e chave

**Uma linha só, cola tudo**:

```
$ sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /etc/ssl/extrator/privkey.pem -out /etc/ssl/extrator/fullchain.pem -config /etc/ssl/extrator/openssl.cnf -extensions v3_req
```

✅ Aparece `Generating a RSA private key ... writing new private key to...`

### 7.4 Proteger a chave

```
$ sudo chmod 600 /etc/ssl/extrator/privkey.pem
$ sudo chmod 644 /etc/ssl/extrator/fullchain.pem
```

---

## PARTE 8 — Buildar o frontend

### 8.1 Entrar na pasta

```
$ cd /opt/extrator-protheus/frontend
```

### 8.2 Instalar dependências do Node

```
$ sudo -u extrator npm ci --no-audit --no-fund
```

Demora 2-5 minutos. Baixa centenas de pacotes.

✅ `added 300+ packages in 2m`

❌ Se der "permission denied" pra alguma pasta node_modules, roda:
```
$ sudo chown -R extrator:extrator /opt/extrator-protheus/frontend
```
E tenta de novo.

### 8.3 Buildar (compila React pra HTML/CSS/JS de produção)

```
$ sudo -u extrator npm run build
```

Demora 20-60 segundos.

✅ No fim aparece `✓ built in Xs` e `dist/index.html ... kB`

Confere que criou:

```
$ ls /opt/extrator-protheus/frontend/dist/
```

✅ Deve ter `index.html` e uma pasta `assets/`.

---

## PARTE 9 — Instalar o backend como serviço systemd

Serviço systemd = o app sobe automático quando a VM liga e reinicia
automático se cair.

### 9.1 Copiar o unit file

```
$ sudo cp /opt/extrator-protheus/deploy/extrator-backend.service /etc/systemd/system/extrator-backend.service
```

### 9.2 Avisar o systemd que tem serviço novo

```
$ sudo systemctl daemon-reload
```

### 9.3 Habilitar (sobe sozinho no boot) e iniciar agora

```
$ sudo systemctl enable extrator-backend
$ sudo systemctl start extrator-backend
```

### 9.4 Confirmar que subiu

```
$ sudo systemctl status extrator-backend
```

✅ Deve mostrar `Active: active (running)` em verde. Aperta `q` pra sair.

❌ Se aparecer `failed`: vê o log pra descobrir o erro:
```
$ sudo journalctl -u extrator-backend -n 50 --no-pager
```
Os erros mais comuns:
- Conexão Postgres → senha errada no `.env`
- Oracle não acessível → firewall/rede bloqueando
- `ModuleNotFoundError` → algo faltou no `pip install`

Me manda o output que resolvo.

### 9.5 Teste direto no backend (via loopback)

```
$ curl http://127.0.0.1:8000/health
```

✅ Retorna um JSON com `"ok": true` (ou com algum serviço false se o Oracle
tiver problema de rede — mas o backend tá rodando).

---

## PARTE 10 — Instalar o Nginx

O Nginx é a "porta de entrada" — recebe o navegador e repassa pro backend
ou serve os arquivos estáticos.

### 10.1 Copiar o config

```
$ sudo cp /opt/extrator-protheus/deploy/nginx-extrator.conf /etc/nginx/sites-available/extrator
```

### 10.2 Ativar o site

```
$ sudo ln -s /etc/nginx/sites-available/extrator /etc/nginx/sites-enabled/
```

### 10.3 Desativar o site padrão do Nginx

```
$ sudo rm -f /etc/nginx/sites-enabled/default
```

### 10.4 Testar a config antes de aplicar

```
$ sudo nginx -t
```

✅ Deve aparecer:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

❌ Se der erro, ele diz a linha exata do problema no arquivo
`/etc/nginx/sites-available/extrator`. Me manda que arrumo.

### 10.5 Aplicar

```
$ sudo systemctl reload nginx
```

Sem output = deu certo.

---

## PARTE 11 — Liberar o firewall (opcional, mas recomendado)

Se o Ubuntu tiver UFW instalado (geralmente tem):

```
$ sudo ufw allow 22/tcp
$ sudo ufw allow 80/tcp
$ sudo ufw allow 443/tcp
$ sudo ufw enable
```

Vai perguntar se tem certeza (pode cortar sua SSH se errar). Como você
liberou a 22 antes, segura responder `y`.

```
$ sudo ufw status
```

✅ Deve mostrar as 3 portas como "ALLOW".

---

## PARTE 12 — TESTE FINAL 🎉

Do seu PC Windows (ou qualquer PC na mesma rede), abre o navegador:

```
https://192.168.3.128/
```

**O que vai acontecer na primeira vez:**

1. **Tela vermelha de "conexão não segura"** — é esperado! Certificado
   self-signed sempre dá isso na primeira visita.
2. Clica em **"Avançado"** (ou "Opções avançadas")
3. Clica em **"Prosseguir para 192.168.3.128 (não seguro)"**
4. Vai lembrar da escolha — só precisa fazer isso uma vez por navegador.

✅ Aparece a tela de login do Extrator Protheus!

5. Logue com o admin que você criou no passo 5.7
6. Testa um relatório, de preferência o SB8 Suzano (não tem filtro, mais rápido)

🎉 **Deploy concluído!**

---

## Como atualizar depois (ciclo normal)

Quando você der `git push` com mudanças novas, conecta na VM e roda:

```
$ sudo -u extrator /opt/extrator-protheus/deploy/deploy.sh
```

Esse script faz TUDO: puxa do git, atualiza deps, roda migrations, rebuilda
frontend, reinicia serviços.

Demora 1-2 minutos. O backend fica indisponível por ~10 segundos durante o
restart.

---

## Troubleshooting (quando der ruim)

### "502 Bad Gateway" no navegador

O backend caiu. Confere:
```
$ sudo systemctl status extrator-backend
$ sudo journalctl -u extrator-backend -n 100 --no-pager
```

### "Conexão recusada" ou "página não encontrada"

O Nginx não tá rodando. Confere:
```
$ sudo systemctl status nginx
```

### Login funciona mas sou deslogado na hora

Você acessou por HTTP em vez de HTTPS. O cookie tem `secure=true`, só
funciona em HTTPS. Confere a URL da barra do navegador — tem que começar
com `https://`.

### "Mixed content" no console do navegador (F12)

Alguma chamada tá indo pra HTTP enquanto a página tá em HTTPS. Me chama.

### Backend sobe mas /health diz Oracle "erro"

Rede. A VM não tá conseguindo falar com o Oracle Protheus. Teste:
```
$ nc -zv IP_DO_ORACLE 1521
```
Se der "connection refused" ou "no route to host", é firewall na rede.
Fala com a TI pra liberar o tráfego da VM pro Oracle.

### Certificado expirou (daqui a 10 anos 😄)

Repete o passo 7.3 (gera um novo com o mesmo comando) e roda:
```
$ sudo systemctl reload nginx
```

---

## Problemas conhecidos (histórico)

Lista de erros que já aconteceram no primeiro deploy e as soluções:

### Alembic: `invalid interpolation syntax` na senha do Postgres

**Causa**: senha contém `@`, `#` ou outro caractere que vira `%XX` na URL, e o
`ConfigParser` do Alembic interpreta `%` como código especial.

**Status no projeto**: já corrigido em `backend/alembic/env.py` (usa
`create_engine` direto, sem passar pelo `ConfigParser`).

### Login retorna 401 mesmo com senha certa + log diz `error reading bcrypt version`

**Causa**: incompatibilidade entre `passlib 1.7.4` e `bcrypt 4.1+`.

**Status no projeto**: já corrigido em `backend/requirements.txt` com
`bcrypt>=4.0,<4.1`.

### Build do frontend falha com `Cannot find module 'path'` ou `__dirname`

**Causa**: falta `@types/node` no `package.json`.

**Status no projeto**: já corrigido.

### Nginx recusa a config com `unknown directive "http2"`

**Causa**: a sintaxe `http2 on;` separada só existe no Nginx 1.25+. O Ubuntu
22.04 vem com Nginx 1.18.

**Status no projeto**: já corrigido em `deploy/nginx-extrator.conf` com a
sintaxe compatível `listen 443 ssl http2;`.

---

## O que fazer quando me chamar

Se travar em algum passo, me manda:

1. **O passo exato** onde parou (ex: "passo 9.4")
2. **O comando que rodou** (copia do terminal)
3. **O output exato** do erro (copia do terminal)

Com isso resolvo em 1 ou 2 mensagens.
