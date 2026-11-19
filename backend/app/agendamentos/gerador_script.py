"""
Gerador do script sincronizador que o usuário instala no PC.

O script é um Python 3 standalone que:
  1. Pergunta uma pasta de destino na 1ª execução (ou lê de arquivo de config)
  2. Chama GET /agendamentos/{id}/execucoes/pendentes?maquina_id=<id>
  3. Pra cada execução pendente, baixa o CSV e salva na pasta
  4. Chama POST /agendamentos/{id}/execucoes/{exec_id}/baixada com sucesso/erro
  5. Encerra.

Rodado via Task Scheduler (Windows) / cron (Linux) / launchd (Mac) de hora em
hora + no login. É quase sem dependências — só `requests` do pip.

Usuário baixa, roda `pip install requests`, depois configura o scheduler do SO
via o passo a passo (Markdown) devolvido junto.
"""
from __future__ import annotations

from typing import Optional

# Importante: o script baixado pelo usuário é código gerado — ele precisa ser
# AUTO-CONTIDO, não pode importar nada do app. Por isso tudo aqui embaixo é
# string, não Python importado.


def _instrucoes_windows() -> str:
    return """# Instalação — Windows

## 1. Pré-requisitos

- **Python 3.9+** instalado (baixe em https://python.org se não tiver)
- Biblioteca `requests`:

  ```powershell
  pip install requests
  ```

## 2. Salvar o script

Salve o arquivo `extrator-sync-{AG_ID}.py` em algum lugar fixo. Sugestão:

```
C:\\Users\\<voce>\\extrator-sync\\extrator-sync-{AG_ID}.py
```

## 3. Rodar a 1ª vez — configurar a pasta de destino

Abra um **PowerShell** nessa pasta e rode:

```powershell
python extrator-sync-{AG_ID}.py --setup
```

Ele pergunta onde salvar os CSVs. Sugestão:
```
C:\\Users\\<voce>\\OneDrive - Technocoat\\Relatorios\\{AG_NOME}
```

Isso grava um arquivo `extrator-sync-{AG_ID}.ini` do lado, com a pasta e um
ID único desse PC.

## 4. Testar

Ainda no PowerShell:

```powershell
python extrator-sync-{AG_ID}.py
```

Se houver execução nova, o CSV aparece na pasta configurada. Se não, imprime
"nada a baixar" — o que é OK.

## 5. Agendar no Task Scheduler

Pra rodar automaticamente de hora em hora + no login:

1. Abra o **Agendador de Tarefas** (`taskschd.msc`)
2. Clique em **Criar Tarefa...** (não "Criar Tarefa Básica")
3. Aba **Geral**:
   - Nome: `Extrator Sync — {AG_NOME}`
   - Marque **Executar com privilégios mais altos**: NÃO (não precisa)
   - Marque **Executar estando o usuário conectado ou não**: SIM (recomendado)
4. Aba **Disparadores** → Novo:
   - Disparador 1: **Diariamente**, hora de início: `00:00:00`, **Repetir tarefa a cada 1 hora** por 1 dia
   - Disparador 2: **Ao fazer logon** do seu usuário
5. Aba **Ações** → Nova:
   - Programa/Script: `python`
   - Argumentos: `"C:\\Users\\<voce>\\extrator-sync\\extrator-sync-{AG_ID}.py"`
   - Iniciar em: `C:\\Users\\<voce>\\extrator-sync\\`
6. Aba **Condições**: desmarque "Iniciar a tarefa só se o computador estiver na rede elétrica" (se for notebook)
7. Aba **Configurações**: marque "Se a tarefa falhar, reiniciar a cada 5 min" (3 tentativas)
8. **OK** — ele pede sua senha pra guardar

## Pronto

A tarefa roda a cada hora. Pra ver histórico: `taskschd.msc` → tarefa → aba **Histórico**.
Logs do script: aparecem no mesmo diretório como `extrator-sync-{AG_ID}.log`.

## Problemas comuns

- **"ModuleNotFoundError: requests"** → `pip install requests` com o mesmo Python
  do PATH. Se usou `py` em vez de `python`, troque na ação do Task Scheduler.
- **Token inválido (401)** → o agendamento foi deletado ou desativado na web.
  Reative ou gere um script novo.
- **Pasta não existe** → o OneDrive foi desinstalado/movido. Rode
  `python extrator-sync-{AG_ID}.py --setup` pra reconfigurar.
"""


def _script_python(
    *,
    agendamento_id: int,
    nome_agendamento: str,
    token_claro: str,
    api_base: str,
) -> str:
    """
    Script sincronizador. Autocontido: usa só stdlib + requests.
    Sem f-strings com { do CSS porque vamos interpolar: uso placeholder {{ }}.
    """
    return f'''"""
Extrator Protheus — Sincronizador local
Agendamento: {nome_agendamento} (#{agendamento_id})
Gerado automaticamente — não edite os valores no topo. Pra reconfigurar a
pasta de destino, rode `python {{nome}} --setup`.
"""
import argparse
import configparser
import logging
import os
import sys
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("Dependência faltando: pip install requests")
    sys.exit(1)

# ===== Configuração embutida (NÃO EDITE) =====
AGENDAMENTO_ID = {agendamento_id}
TOKEN = {token_claro!r}
API_BASE = {api_base!r}
VERSAO = "1.0"
# =============================================

AQUI = Path(__file__).resolve().parent
CONFIG_PATH = AQUI / f"extrator-sync-{{AGENDAMENTO_ID}}.ini"
LOG_PATH = AQUI / f"extrator-sync-{{AGENDAMENTO_ID}}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("extrator-sync")


def carregar_ou_pedir_config():
    """Lê ini local. Se não existir, roda o wizard."""
    if not CONFIG_PATH.exists():
        return setup_interativo()
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    try:
        pasta = Path(cfg["sync"]["pasta_destino"]).expanduser()
        maquina_id = cfg["sync"]["maquina_id"]
    except KeyError:
        return setup_interativo()
    if not pasta.exists():
        log.warning("Pasta de destino %s não existe — recriando.", pasta)
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log.error("Falha ao criar pasta: %s", e)
            sys.exit(1)
    return pasta, maquina_id


def setup_interativo():
    """Pergunta a pasta, gera maquina_id, escreve o ini."""
    print(f"== Setup do Extrator Sync (agendamento #{{AGENDAMENTO_ID}}) ==")
    padrao = str(Path.home() / "Downloads" / "ExtratorProtheus")
    print(f"Onde salvar os CSVs? (ENTER usa '{{padrao}}')")
    entrada = input("> ").strip() or padrao
    pasta = Path(entrada).expanduser()
    pasta.mkdir(parents=True, exist_ok=True)
    maquina_id = f"{{os.environ.get('COMPUTERNAME') or os.uname().nodename}}-{{uuid.uuid4().hex[:8]}}"
    cfg = configparser.ConfigParser()
    cfg["sync"] = {{
        "pasta_destino": str(pasta),
        "maquina_id": maquina_id,
    }}
    with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
        cfg.write(fp)
    print(f"OK! Salvando em: {{pasta}}")
    print(f"ID desta máquina: {{maquina_id}}")
    return pasta, maquina_id


def _url(path: str) -> str:
    return f"{{API_BASE.rstrip('/')}}{{path}}"


def _headers():
    return {{"X-Agendamento-Token": TOKEN, "User-Agent": f"extrator-sync/{{VERSAO}}"}}


def listar_pendentes(maquina_id: str):
    r = requests.get(
        _url(f"/agendamentos/{{AGENDAMENTO_ID}}/execucoes/pendentes"),
        params={{"maquina_id": maquina_id}},
        headers=_headers(),
        timeout=30,
    )
    if r.status_code == 401:
        log.error("Token inválido (401). O agendamento foi desativado ou removido.")
        sys.exit(2)
    r.raise_for_status()
    return r.json()


def baixar_execucao(exec_: dict, pasta: Path) -> Path:
    url = _url(exec_["download_url"])
    nome_arq = exec_.get("nome_arquivo") or f"exec-{{exec_['id']}}.csv"
    destino = pasta / nome_arq
    with requests.get(url, headers=_headers(), stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(destino, "wb") as fp:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    fp.write(chunk)
    return destino


def callback(exec_id: int, maquina_id: str, ok: bool, erro: str | None = None):
    try:
        requests.post(
            _url(f"/agendamentos/{{AGENDAMENTO_ID}}/execucoes/{{exec_id}}/baixada"),
            json={{"maquina_id": maquina_id, "ok": ok, "erro": erro}},
            headers=_headers(),
            timeout=15,
        )
    except Exception as e:
        log.warning("Callback falhou pra exec %s (não-fatal): %s", exec_id, e)


def main():
    parser = argparse.ArgumentParser(description="Extrator Protheus — Sincronizador local")
    parser.add_argument("--setup", action="store_true", help="Reconfigurar pasta de destino")
    args = parser.parse_args()

    if args.setup:
        setup_interativo()
        return 0

    pasta, maquina_id = carregar_ou_pedir_config()
    log.info("iniciando sync (pasta=%s maquina=%s)", pasta, maquina_id)

    try:
        pendentes = listar_pendentes(maquina_id)
    except requests.RequestException as e:
        log.error("Falha ao consultar API: %s", e)
        return 1

    if not pendentes:
        log.info("nada a baixar")
        return 0

    log.info("%d execução(ões) pendente(s)", len(pendentes))
    ok_count = err_count = 0
    for exec_ in pendentes:
        exec_id = exec_["id"]
        nome = exec_.get("nome_arquivo") or f"exec-{{exec_id}}"
        try:
            destino = baixar_execucao(exec_, pasta)
            log.info("OK %s -> %s", nome, destino)
            callback(exec_id, maquina_id, ok=True)
            ok_count += 1
        except Exception as e:
            log.error("FALHA %s: %s", nome, e)
            callback(exec_id, maquina_id, ok=False, erro=str(e))
            err_count += 1

    log.info("fim — %d ok, %d erro(s)", ok_count, err_count)
    return 0 if err_count == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
'''


def gerar_para_windows(
    *,
    agendamento_id: int,
    nome_agendamento: str,
    token_claro: str,
    api_base: str,
) -> tuple[str, str, str, str]:
    """
    Gera (nome_arquivo, conteudo_script, instrucoes_markdown, extensao).
    """
    nome_arq = f"extrator-sync-{agendamento_id}.py"
    conteudo = _script_python(
        agendamento_id=agendamento_id,
        nome_agendamento=nome_agendamento,
        token_claro=token_claro,
        api_base=api_base,
    )
    instr = _instrucoes_windows().replace("{AG_ID}", str(agendamento_id)).replace(
        "{AG_NOME}", nome_agendamento
    )
    return nome_arq, conteudo, instr, "py"


def gerar_para_so(
    so: str,
    *,
    agendamento_id: int,
    nome_agendamento: str,
    token_claro: str,
    api_base: str,
) -> tuple[str, str, str, str]:
    """
    Dispatcher por OS. Hoje só windows está implementado (etapa A=a).
    Linux e Mac usam o MESMO .py — só o passo-a-passo muda; adicionar depois.
    """
    if so == "windows":
        return gerar_para_windows(
            agendamento_id=agendamento_id,
            nome_agendamento=nome_agendamento,
            token_claro=token_claro,
            api_base=api_base,
        )
    raise ValueError(f"Sistema operacional ainda não suportado: {so!r}. Hoje: windows.")
