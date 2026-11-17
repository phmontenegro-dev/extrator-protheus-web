# Como adicionar um novo relatório pronto

Guia passo a passo para criar um novo "relatório pronto" (com regras de
negócio específicas, extração + tratamento). Uma vez que a arquitetura tá
pronta, adicionar um relatório é basicamente:

1. Criar 2 arquivos Python no backend (`extrair.py` + `tratar.py`)
2. Registrar no `registry.py`
3. Adicionar um endpoint no `relatorios.py`
4. (Opcional) Adicionar um ícone no menu
5. Liberar a permissão pros usuários via painel admin

**Zero mudança no frontend** — o `RelatorioGenerico.tsx` já atende os 3 tipos
de filtros existentes automaticamente.

---

## Antes de começar — decidir o tipo de filtros

O frontend renderiza o formulário certo baseado no campo `filtros` do
registry. As opções existentes hoje:

| `filtros` | O que o usuário preenche | Exemplos |
|---|---|---|
| `"nenhum"` | Nada. Só clica "Extrair CSV" | SB8 Suzano, SD1 Suzano |
| `"periodo"` | 2 campos de data (ini + fim) | CT2010, SFT010, SD3010 |
| `"filial_periodo"` | 1 campo filial + 2 campos data | QPR010 |
| `"livre"` | Interface especial do Relatório Livre | (interno, não usar) |

Se seu relatório precisa de **outros filtros** (ex: vários produtos, cliente
específico, etc), aí precisa criar uma nova UI — é o escopo da Etapa 12
(filtros dinâmicos). Até lá, adapte um dos 3 tipos existentes.

---

## Passo 1 — Criar a pasta do relatório

Digamos que você vai criar um **"SA1 — Cadastro de Clientes"** sem filtros.
Convenção de nome do id: minúsculo, snake_case, igual aos outros.

```bash
mkdir -p backend/app/relatorios_prontos/sa1_clientes
touch backend/app/relatorios_prontos/sa1_clientes/__init__.py
```

## Passo 2 — Criar `extrair.py`

**Template** — copia, cola e adapta:

```python
"""
Extração do SA1010 — Cadastro de Clientes.

[Descreva aqui o que o relatório faz, quais filtros fixos, etc.]
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sa1_clientes() -> pd.DataFrame:
    """
    Extrai o cadastro de clientes ativos.
    [Explique os parâmetros, se houver.]
    """
    query = """
        SELECT
            A1_COD,
            A1_LOJA,
            A1_NOME,
            A1_NREDUZ,
            A1_CGC,
            A1_MUN,
            A1_EST,
            A1_TEL
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

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["A1_COD", "A1_LOJA", "A1_CGC", "A1_EST"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
```

### Com filtros de PERÍODO

Se fosse `"periodo"`, a função receberia 2 strings `AAAAMMDD`:

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
        df = pd.read_sql(
            query, conn,
            params={"data_inicio": data_inicio, "data_fim": data_fim},
        )
    finally:
        conn.close()
    return df
```

### Com filtros de FILIAL + PERÍODO

Se fosse `"filial_periodo"`, 3 parâmetros:

```python
def extrair_meu_relatorio(filial: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    query = """
        SELECT ...
        FROM MINHA_TABELA
        WHERE MINHA_FILIAL = :filial
          AND MINHA_DATA BETWEEN :data_inicio AND :data_fim
          AND D_E_L_E_T_ = ' '
    """
    params = {"filial": filial, "data_inicio": data_inicio, "data_fim": data_fim}
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()
    return df
```

### Regras importantes

- **Sempre** use `get_oracle_connection()` (de `app.oracle`), NÃO `oracledb.connect()` direto.
- **Sempre** inclua `D_E_L_E_T_ = ' '` em cada tabela do Protheus.
- **Sempre** use bind variables (`:data_inicio`) para valores — nunca interpole.
- Faça `strip()` nos códigos para preservar zeros à esquerda.
- Fechar a conexão com `conn.close()` dentro do `finally`.

## Passo 3 — Criar `tratar.py`

**Template** — base que você adapta:

```python
"""
Tratamento pós-extração do SA1 Clientes.

Regras aplicadas:
  1. Strip em colunas texto.
  2. Renomear para nomes amigáveis.
  3. Formatar CPF/CNPJ.
  4. Ordem final de colunas.
"""
import pandas as pd


RENOMEAR = {
    "A1_COD":    "CODIGO",
    "A1_LOJA":   "LOJA",
    "A1_NOME":   "RAZAO SOCIAL",
    "A1_NREDUZ": "NOME FANTASIA",
    "A1_CGC":    "CNPJ/CPF",
    "A1_MUN":    "MUNICIPIO",
    "A1_EST":    "UF",
    "A1_TEL":    "TELEFONE",
}

ORDEM_FINAL = [
    "CODIGO",
    "LOJA",
    "RAZAO SOCIAL",
    "NOME FANTASIA",
    "CNPJ/CPF",
    "MUNICIPIO",
    "UF",
    "TELEFONE",
]


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    # 1) Strip em colunas texto.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # 2) Renomear.
    df = df.rename(columns=RENOMEAR)

    # 3) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]
    return df
```

### Helpers úteis que os outros relatórios já têm

Copie do `ct2010/tratar.py`, `sd3010/tratar.py` ou `sft010/tratar.py` quando precisar:

**Data AAAAMMDD → DD/MM/AAAA**:
```python
def _formatar_data(valor) -> str:
    if not isinstance(valor, str):
        return valor
    v = valor.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
    return v
```

**Numérico com vírgula**:
```python
def _formatar_numero(x, casas: int) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)
```

**Juntar data + hora**:
```python
def _consolidar_data_hora(df, col_data, col_hora, nome_final):
    if col_data not in df.columns:
        return df
    datas = df[col_data].apply(_formatar_data)
    if col_hora in df.columns:
        horas = df[col_hora].apply(_formatar_hora)
        df[nome_final] = (datas.fillna("") + " " + horas.fillna("")).str.strip()
        df = df.drop(columns=[col_hora])
    else:
        df[nome_final] = datas
    df = df.drop(columns=[col_data])
    return df
```

## Passo 4 — Registrar no `registry.py`

Abre `backend/app/relatorios_prontos/registry.py` e adiciona uma entrada na
lista `RELATORIOS`:

```python
    {
        "id": "sa1_clientes",
        "nome": "SA1 — Cadastro de Clientes",
        "descricao": "Lista todos os clientes ativos com dados cadastrais básicos.",
        "filtros": "nenhum",
    },
```

Posição na lista não importa — o frontend ordena pelo nome.

## Passo 5 — Adicionar o endpoint em `routers/relatorios.py`

Abre `backend/app/routers/relatorios.py`.

**5.1 — Importa as funções novas** (perto dos outros imports do topo):

```python
from app.relatorios_prontos.sa1_clientes.extrair import extrair_sa1_clientes
from app.relatorios_prontos.sa1_clientes.tratar import tratar_dataframe as tratar_sa1_clientes
```

**5.2 — Cria o endpoint**. Se o relatório é `"nenhum"`:

```python
@router.post("/sa1_clientes/extrair")
def sa1_clientes(request: Request,
                 db: Session = Depends(get_db),
                 usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sa1_clientes",
        nome_arquivo="SA1_Clientes.csv",
        extrair_fn=lambda: extrair_sa1_clientes(),
        tratar_fn=tratar_sa1_clientes,
    )
```

### Variações do endpoint

**Com período**:
```python
@router.post("/meu_id/extrair")
def meu_id(filtros: FiltrosPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="meu_id",
        nome_arquivo=f"MeuID_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_meu_relatorio(di, df),
        tratar_fn=tratar_meu_relatorio,
        parametros_log={"data_inicio": di, "data_fim": df},
    )
```

**Com filial + período**:
```python
@router.post("/meu_id/extrair")
def meu_id(filtros: FiltrosFilialPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    filial = filtros.filial.strip()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="meu_id",
        nome_arquivo=f"MeuID_{filial}_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_meu_relatorio(filial, di, df),
        tratar_fn=tratar_meu_relatorio,
        parametros_log={"filial": filial, "data_inicio": di, "data_fim": df},
    )
```

### O que o `executar_e_responder_csv` faz por você

- ✅ Verifica se o usuário tem permissão (403 se não tiver)
- ✅ Chama `extrair_fn()` e checa se veio vazio (404 "sem registros")
- ✅ Chama `tratar_fn(df)` se definido
- ✅ Serializa pra CSV (`;` separador, UTF-8 com BOM, pronto pra Excel)
- ✅ Devolve `StreamingResponse` com `Content-Disposition: attachment`
- ✅ Grava log em `logs_acesso` com duração, nº de linhas, parâmetros
- ✅ Captura qualquer exceção → 500 com mensagem + log de falha

Você não precisa pensar em nada disso.

## Passo 6 — (Opcional) Ícone no menu

Em `frontend/src/pages/Menu.tsx`, mapa `ICONES`:

```tsx
const ICONES: Record<string, typeof FileSpreadsheet> = {
  ct2010: ScrollText,
  qpr010: Beaker,
  // ...
  sa1_clientes: Users,   // ← adiciona o seu com ícone da lucide-react
}
```

Se não adicionar, ganha o ícone padrão `FileSpreadsheet` — também fica bom.
Lista de ícones disponíveis: https://lucide.dev/icons

## Passo 7 — Testar localmente

Em dev:

```bash
# Backend — reinicia pra pegar o endpoint novo
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Como admin, abre o navegador no `http://localhost:5173/menu`. O card novo
aparece junto com os outros. Clica → extração roda → CSV baixa.

## Passo 8 — Liberar pros usuários

No painel `/admin/usuarios/:id`, cada usuário não-admin precisa ter o
relatório marcado nas permissões. **Admin** vê tudo automaticamente.

## Passo 9 — Deploy em produção

```bash
# No PC
git add .
git commit -m "feat(relatorios): adiciona SA1 Clientes"
git push

# Na VM
cd /opt/extrator-protheus
sudo -u extrator git pull
sudo -u extrator /opt/extrator-protheus/deploy/deploy.sh
```

---

## Checklist completo

Pra não esquecer nada:

- [ ] `backend/app/relatorios_prontos/<id>/__init__.py` (vazio)
- [ ] `backend/app/relatorios_prontos/<id>/extrair.py` com função `extrair_<id>`
- [ ] `backend/app/relatorios_prontos/<id>/tratar.py` com função `tratar_dataframe`
- [ ] Entrada em `RELATORIOS` no `registry.py`
- [ ] 2 imports novos em `routers/relatorios.py` (extrair + tratar)
- [ ] Endpoint `@router.post("/<id>/extrair")` no mesmo arquivo
- [ ] (Opcional) Ícone no `ICONES` do `Menu.tsx`
- [ ] Testou localmente e baixou o CSV
- [ ] Liberou permissão pros usuários não-admin no painel
- [ ] `git push` + `deploy.sh` na VM

---

## Resumo visual da estrutura

```
backend/app/
├── relatorios_prontos/
│   ├── registry.py            ← adiciona entry aqui
│   ├── ct2010/                ← modelo rico (período + PROCV + CV3)
│   ├── sb8_suzano/            ← modelo sem filtros (mais simples)
│   ├── qpr010/                ← modelo com filial+período
│   └── sa1_clientes/          ← ← ← SEU NOVO AQUI
│       ├── __init__.py
│       ├── extrair.py
│       └── tratar.py
└── routers/
    └── relatorios.py          ← adiciona imports + endpoint aqui
```

---

## Perguntas frequentes

**Posso usar imports de módulos externos (requests, numpy, etc)?**
Sim, mas adiciona a dep em `requirements.txt` e roda `pip install -r
requirements.txt` na VM depois do deploy.

**E se o relatório não precisar de tratamento (CSV cru)?**
Passa `tratar_fn=None` no `executar_e_responder_csv`. Não precisa criar
`tratar.py`, mas deixa o arquivo vazio pra manter o padrão.

**Preciso rodar migration do Alembic?**
Não — relatórios prontos não mexem na estrutura do banco interno.
Migrations só são necessárias se você mudar modelos SQLAlchemy em
`app/models/`.

**O usuário consegue ver o relatório imediatamente após o deploy?**
Só se for admin. Usuários comuns precisam que você libere a permissão
individualmente em `/admin/usuarios/:id`.

**Posso reutilizar a `apoio.py` do CT2010 (planilhas de PROCV)?**
Sim — se seu novo relatório precisar enriquecer dados com as mesmas
planilhas, importa de `app.relatorios_prontos.ct2010.apoio`.

**Como vou debugar quando der erro?**
Logs do backend em tempo real: `sudo journalctl -u extrator-backend -f`.
Toda falha de extração também cai em `logs_acesso` com `erro_mensagem`
detalhado — consulta via `/admin/logs` ou `sudo -u postgres psql -d
extrator` + SELECT.
