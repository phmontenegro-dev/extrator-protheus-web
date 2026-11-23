# Como adicionar um novo relatório pronto

A partir da Etapa 11.6 (auto-descoberta), adicionar um relatório é
basicamente **criar 1 pacote com 3 arquivos**. O backend descobre
sozinho no startup — zero edição em routers, runners, registry ou
qualquer outro arquivo.

## Visão geral

```
backend/app/relatorios_prontos/<id>/
├── __init__.py        ← registra o relatório (uma declaração)
├── extrair.py         ← roda o SQL no Oracle, devolve DataFrame
└── tratar.py          ← renomeia colunas, formata, reordena
```

Pronto. Restart do backend e o relatório aparece no menu.

---

## Antes de começar — decidir o tipo de filtros

| `filtros` | O que o usuário preenche | Exemplos |
|---|---|---|
| `"nenhum"` | Nada. Só clica "Extrair" | SB8 Suzano, SD1 Suzano |
| `"periodo"` | 2 campos de data (ini + fim) | CT2010, SFT010, SD3010 |
| `"filial_periodo"` | 1 campo filial + 2 campos data | QPR010 |

Se seu relatório precisa de **outros filtros** (multi-select, cliente
específico, etc), aí precisa criar UI custom — não cabe no modelo
atual. Até lá, adapte um dos 3 tipos existentes.

---

## Passo 1 — Criar a pasta

Digamos que você vai criar um **"SA1 — Cadastro de Clientes"** sem filtros.
Convenção de id: minúsculo, snake_case, único.

```bash
mkdir -p backend/app/relatorios_prontos/sa1_clientes
```

## Passo 2 — Criar `extrair.py`

Template base:

```python
"""
Extração do SA1010 — Cadastro de Clientes.
Explique aqui o que o relatório faz e quais filtros fixos usa.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sa1_clientes() -> pd.DataFrame:
    """Extrai o cadastro de clientes ativos."""
    query = """
        SELECT
            A1_COD, A1_LOJA, A1_NOME, A1_NREDUZ, A1_CGC, A1_MUN, A1_EST, A1_TEL
        FROM SA1010
        WHERE A1_MSBLQL = '2'
          AND D_E_L_E_T_ = ' '
        ORDER BY A1_NOME
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    for col in ["A1_COD", "A1_LOJA", "A1_CGC", "A1_EST"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df
```

### Variações por tipo de filtro

**Período** — função recebe 2 strings `AAAAMMDD`:

```python
def extrair_meu_relatorio(data_inicio: str, data_fim: str) -> pd.DataFrame:
    query = """
        SELECT ...
        FROM MINHA_TABELA
        WHERE MINHA_DATA BETWEEN :data_inicio AND :data_fim
          AND D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn,
                         params={"data_inicio": data_inicio, "data_fim": data_fim})
    finally:
        conn.close()
    return df
```

**Filial + período** — 3 parâmetros:

```python
def extrair_meu_relatorio(filial: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    # mesma coisa, só com +1 bind variable
    ...
```

### Regras do Protheus — sempre seguir

- `get_oracle_connection()` de `app.oracle`, NÃO `oracledb.connect()` direto
- `D_E_L_E_T_ = ' '` em cada tabela Protheus (filtra deletados)
- Bind variables (`:data_inicio`) — nunca interpole valores
- `strip()` em códigos pra preservar zeros à esquerda
- Fechar conexão no `finally`
- Nomes de tabela sempre com sufixo `010`: `SB1010`, `CYN010`, `SH1010`. Se
  seu SQL vier de outra ferramenta citando sem sufixo (ex: `FROM CYN C`),
  CORRIJA pra `CYN010`

## Passo 3 — Criar `tratar.py`

Template base:

```python
"""Tratamento pós-extração do SA1 Clientes."""
import pandas as pd


RENOMEAR = {
    "A1_COD":    "CODIGO",
    "A1_NOME":   "RAZAO SOCIAL",
    "A1_CGC":    "CNPJ/CPF",
    "A1_MUN":    "MUNICIPIO",
    "A1_EST":    "UF",
    "A1_TEL":    "TELEFONE",
}

ORDEM_FINAL = [
    "CODIGO", "RAZAO SOCIAL", "CNPJ/CPF", "MUNICIPIO", "UF", "TELEFONE",
]


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    df = df.rename(columns=RENOMEAR)
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]
    return df
```

### Helpers úteis (copie dos outros relatórios quando precisar)

**Data `AAAAMMDD` → `DD/MM/AAAA`**:
```python
def _formatar_data(valor) -> str:
    if not isinstance(valor, str): return valor
    v = valor.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
    return v
```

**Numérico com vírgula**:
```python
def _formatar_numero(x, casas: int) -> str:
    if pd.isna(x): return ""
    try:    return f"{float(x):.{casas}f}".replace(".", ",")
    except: return str(x)
```

## Passo 4 — Criar `__init__.py` — a declaração

**Esse é O arquivo que faz o relatório existir no sistema.** O backend varre
`app.relatorios_prontos.*` e encontra o objeto `relatorio`.

```python
"""Registro do SA1 Clientes no sistema."""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sa1_clientes.extrair import extrair_sa1_clientes
from app.relatorios_prontos.sa1_clientes.tratar import tratar_dataframe


# Wrapper: aceita **kwargs do despachante central e repassa pros args certos.
# Pra "nenhum", basta ignorar tudo. Pra "periodo", pega data_inicio/data_fim.
# Pra "filial_periodo", pega filial + datas.
def _extrair(**_):
    return extrair_sa1_clientes()


relatorio = RelatorioPronto(
    id="sa1_clientes",                          # mesmo nome da pasta
    nome="SA1 — Cadastro de Clientes",          # aparece no menu
    descricao="Lista todos os clientes ativos com dados cadastrais básicos.",
    filtros="nenhum",                           # "nenhum" | "periodo" | "filial_periodo"
    extrair=_extrair,
    tratar=tratar_dataframe,
)
```

### Para `filtros="periodo"`:

```python
def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_meu_relatorio(data_inicio, data_fim)

relatorio = RelatorioPronto(
    id="meu_id",
    nome="...",
    descricao="...",
    filtros="periodo",
    extrair=_extrair,
    tratar=tratar_dataframe,
)
```

### Para `filtros="filial_periodo"`:

```python
def _extrair(filial: str, data_inicio: str, data_fim: str, **_):
    return extrair_meu_relatorio(filial, data_inicio, data_fim)

relatorio = RelatorioPronto(
    id="meu_id",
    ...
    filtros="filial_periodo",
    extrair=_extrair,
    tratar=tratar_dataframe,
)
```

> **Por que o wrapper `_extrair`?** O despachante central passa TODOS os
> filtros como `**kwargs`. Se sua função já aceita kwargs, pode usar direto
> em `extrair=`. O wrapper existe só pra isolar as assinaturas antigas de
> `extrair.py` que são posicionais.

### Nome de arquivo (opcional)

Por padrão, o CSV baixado se chama:
- `MEU_ID.csv` (sem filtros)
- `MEU_ID_AAAAMMDD_a_AAAAMMDD.csv` (período)
- `MEU_ID_FILIAL_AAAAMMDD_a_AAAAMMDD.csv` (filial + período)

Pra customizar, passa `nome_arquivo_template`:

```python
relatorio = RelatorioPronto(
    ...,
    nome_arquivo_template="SA1_Clientes_{data_inicio}_a_{data_fim}.csv",
)
```

Placeholders disponíveis: `{data_inicio}`, `{data_fim}`, `{filial}` (quando aplicável).

---

## Passo 5 — Reiniciar o backend

```bash
sudo systemctl restart extrator-backend
sudo systemctl restart extrator-scheduler   # se tiver agendamento recorrente
```

E no log você vai ver:

```
auto-descoberta: 12 relatórios registrados
```

Se seu relatório deu erro de importação, aparece no `journalctl -u extrator-backend`
com stack trace.

---

## Passo 6 — Ajustes no frontend (opcionais)

### 6.1 — Ícone no menu

Hoje cada card no menu principal tem um ícone (ex: 🧾 pro CT2010). Se você
não configurar, seu relatório ganha o ícone padrão `FileSpreadsheet`.

Edita `frontend/src/pages/Menu.tsx`:

**a)** Import no topo:
```tsx
import { ..., Users } from 'lucide-react'   // Users é um exemplo
```

**b)** Entrada no mapa `ICONES`:
```tsx
const ICONES: Record<string, typeof FileSpreadsheet> = {
  ct2010: ScrollText,
  // ...
  sa1_clientes: Users,
}
```

Catálogo de ícones: https://lucide.dev/icons.

### 6.2 — Atribuir a uma área (sem código)

Login como admin → `/admin/areas` → na seção "Atribuições", encontra o
relatório recém-criado e seleciona a área (Contábil, Fiscal, etc). Se
não atribuir, ele cai em "Outros" no menu.

### 6.3 — Build do frontend em produção

Se mexeu no `Menu.tsx`:

```bash
cd /opt/extrator-protheus/frontend
sudo -u extrator npm run build
```

### 6.4 — Liberar permissão (sem código)

Admin vê tudo automaticamente. Usuário comum precisa ter a permissão
marcada em `/admin/usuarios/:id`.

---

## Testar

Em dev:

```bash
cd backend
uvicorn app.main:app --reload
```

Como admin, abre `http://localhost:5173/menu`. O card novo aparece junto
com os outros.

---

## Deploy em produção

```bash
# PC
git add .
git commit -m "feat(relatorios): adiciona SA1 Clientes"
git push

# VM
cd /opt/extrator-protheus
sudo -u extrator git pull
sudo systemctl restart extrator-backend extrator-scheduler
```

---

## Checklist completo

**Backend** (obrigatório):
- [ ] `backend/app/relatorios_prontos/<id>/extrair.py`
- [ ] `backend/app/relatorios_prontos/<id>/tratar.py`
- [ ] `backend/app/relatorios_prontos/<id>/__init__.py` com `relatorio = RelatorioPronto(...)`
- [ ] `sudo systemctl restart extrator-backend`

**Frontend** (opcional):
- [ ] Import do ícone no topo do `Menu.tsx` + entrada no `ICONES`
- [ ] `npm run build` em produção

**Pós-deploy pelo painel admin** (sem código):
- [ ] Atribuiu área em `/admin/areas` (ou deixou em "Outros")
- [ ] Liberou permissão pros usuários em `/admin/usuarios/:id`

---

## Variante: relatório em 1 único arquivo (sem subpasta)

Se o relatório é simples e cabe num arquivo só, você também pode:

```
backend/app/relatorios_prontos/sa1_clientes.py   ← tudo aqui
```

Com o conteúdo:

```python
import pandas as pd
from app.oracle import get_oracle_connection
from app.relatorios_prontos.base import RelatorioPronto


def _extrair(**_):
    query = "SELECT A1_COD, A1_NOME FROM SA1010 WHERE D_E_L_E_T_ = ' '"
    conn = get_oracle_connection()
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def _tratar(df):
    return df.rename(columns={"A1_COD": "CODIGO", "A1_NOME": "RAZAO SOCIAL"})


relatorio = RelatorioPronto(
    id="sa1_clientes",
    nome="SA1 — Cadastro de Clientes",
    descricao="...",
    filtros="nenhum",
    extrair=_extrair,
    tratar=_tratar,
)
```

Use pasta pros relatórios com muita lógica (CT2010 tem `apoio.py` pra
carregar planilhas). Use arquivo único pros simples.

---

## Perguntas frequentes

**Esqueci de registrar em algum arquivo central e dá 500?**
Isso não existe mais. O único lugar que o relatório precisa aparecer é no
`__init__.py` dele próprio. Se o relatório não aparece no menu depois do
restart, checa o `journalctl -u extrator-backend -n 50` — normalmente é
erro de sintaxe ou import no seu próprio código.

**Preciso rodar migration do Alembic?**
Não — relatórios prontos não mexem na estrutura do banco interno.

**Posso reutilizar helpers de outros relatórios (ex: `apoio.py` do CT2010)?**
Sim, é só importar: `from app.relatorios_prontos.ct2010.apoio import ...`.

**Como vou debugar quando der erro?**
Logs em tempo real: `sudo journalctl -u extrator-backend -f`. Toda falha
de extração também cai em `logs_acesso` com `erro_mensagem` — veja em
`/admin/logs`.

**O ID no `__init__.py` precisa bater com o nome da pasta?**
Idealmente sim (ajuda a achar), mas o loader só olha o campo `id` dentro
do `RelatorioPronto`. Se divergir, não quebra — só fica confuso de achar.
