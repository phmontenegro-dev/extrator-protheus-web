"""
Validador defensivo pra SQL livre executado via /sql-livre/*.

O usuário Oracle do .env já é read-only (decisão operacional da Technocoat),
MAS NÃO confiamos só nisso — essas travas aqui são defesa em profundidade:

  1. SQL precisa começar com SELECT ou WITH (ignorando espaços/comentários)
  2. Rejeita qualquer palavra-chave DDL/DML/controle de transação
  3. Rejeita múltiplas sentenças (SELECT 1; SELECT 2 → bloqueado)
  4. Rejeita construções Oracle de execução (DBMS_*, UTL_*, procedural blocks)

Tudo isso previne problemas como:
  - Esquecer e tentar UPDATE sem WHERE
  - Query maliciosa via PL/SQL anônimo
  - Múltiplos statements via '; INSERT ...'
"""
import re


class SqlInvalidoError(ValueError):
    """Lança quando o SQL não passa na validação de segurança."""


# Palavras-chave absolutamente proibidas em QUALQUER posição.
# Match é por "palavra inteira" (fronteira \b) e case-insensitive.
PALAVRAS_BLOQUEADAS = [
    # DML de escrita
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    # DDL
    "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "COMMENT",
    # Controle de permissão
    "GRANT", "REVOKE",
    # Transação (sem efeito em read-only, mas pelo sim pelo não)
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    # Execução procedural
    "EXEC", "EXECUTE", "CALL", "DECLARE", "BEGIN",
    # Lock / admin
    "LOCK", "ANALYZE", "AUDIT", "FLASHBACK", "PURGE",
    # Pacotes Oracle potencialmente perigosos
    "DBMS_", "UTL_", "DBMS_OUTPUT", "DBMS_SQL",
]

# Precompilados em uma única expressão (performance e legibilidade)
_RE_PALAVRA_BLOQUEADA = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in PALAVRAS_BLOQUEADAS) + r")\b",
    re.IGNORECASE,
)

# Primeiro token "significativo" do SQL (ignora espaços/comentários).
# Aceitamos só SELECT ou WITH.
_RE_PRIMEIRO_TOKEN = re.compile(r"\s*(?:--[^\n]*\n|/\*.*?\*/|\s)*(\w+)", re.DOTALL)


def _remover_strings_e_comentarios(sql: str) -> str:
    """
    Remove tudo dentro de strings literais '...' e comentários (-- ... e /* ... */)
    antes da varredura de palavras-chave. Isso evita falso positivo em casos
    como `SELECT 'DROP TABLE foo' FROM dual` (que é legítimo).
    """
    # Comentários de linha
    sem_line_comments = re.sub(r"--[^\n]*", "", sql)
    # Comentários de bloco
    sem_block_comments = re.sub(r"/\*.*?\*/", "", sem_line_comments, flags=re.DOTALL)
    # Strings literais Oracle usam '...' (com '' para aspas internas).
    # Trocamos conteúdo por vazio pra análise. Regex básica funciona pra 99%.
    sem_strings = re.sub(r"'(?:''|[^'])*'", "''", sem_block_comments)
    return sem_strings


def _contem_ponto_virgula_de_separacao(sql_limpo: str) -> bool:
    """
    Verifica se há ';' separando múltiplas sentenças. Um ';' sozinho no fim
    não conta como separação — conta apenas quando há conteúdo não-vazio
    (não-espaço/não-comentário) depois dele.
    """
    partes = sql_limpo.split(";")
    if len(partes) <= 1:
        return False
    # Se depois de algum ';' houver conteúdo não vazio, é múltiplas sentenças
    for parte in partes[1:]:
        if parte.strip():
            return True
    return False


def validar_sql(sql: str) -> str:
    """
    Valida o SQL recebido. Lança SqlInvalidoError em qualquer problema.
    Retorna o SQL limpo (strip + sem ';' final) pronto pra execução.
    """
    if not sql or not sql.strip():
        raise SqlInvalidoError("SQL vazio.")

    sql_trim = sql.strip()

    # 1) Tira strings e comentários pra análise (não mexe no original)
    sql_para_analise = _remover_strings_e_comentarios(sql_trim)

    # 2) Primeiro token precisa ser SELECT ou WITH
    m = _RE_PRIMEIRO_TOKEN.match(sql_para_analise)
    if not m:
        raise SqlInvalidoError("SQL não começa com uma sentença reconhecível.")
    primeiro = m.group(1).upper()
    if primeiro not in ("SELECT", "WITH"):
        raise SqlInvalidoError(
            f"Apenas SELECT e WITH são permitidos aqui. "
            f"Sua consulta começa com '{primeiro}'."
        )

    # 3) Palavras-chave bloqueadas (verificação em texto já sem strings)
    encontradas = _RE_PALAVRA_BLOQUEADA.findall(sql_para_analise)
    if encontradas:
        # Lista deduplicada e ordenada pra mensagem clara
        unicas = sorted({p.upper() for p in encontradas})
        raise SqlInvalidoError(
            f"SQL contém palavra-chave não permitida: {', '.join(unicas)}. "
            f"Apenas consultas SELECT são autorizadas."
        )

    # 4) Múltiplas sentenças
    if _contem_ponto_virgula_de_separacao(sql_para_analise):
        raise SqlInvalidoError(
            "Múltiplas sentenças SQL detectadas. Execute uma consulta por vez."
        )

    # OK — devolve o SQL original, tirando apenas ';' final solto
    # (Oracle não aceita ';' terminador em cursor.execute, mas em PL/SQL block sim).
    sql_pronto = sql_trim.rstrip().rstrip(";").rstrip()
    return sql_pronto
