"""
Conexão com o Oracle Protheus (somente leitura).

Mesmo padrão do desktop — credenciais vêm do .env via config.Settings.
Agora com call_timeout aplicado (em milissegundos): queries que ultrapassam
o timeout são abortadas, evitando que uma consulta travada prenda recursos.
"""
import oracledb

from app.config import get_settings


def get_oracle_connection(timeout_s: int | None = None):
    """
    Abre uma conexão nova com o Oracle Protheus e aplica call_timeout.

    Importante: o call_timeout é em milissegundos. Cada chamada ao banco
    (execute, fetch) respeita esse limite individualmente.

    Args:
        timeout_s: sobrescreve o timeout padrão do .env (ORACLE_QUERY_TIMEOUT_S).
                   Útil para consultas ad-hoc (SQL livre) que devem ter um
                   limite mais apertado que relatórios programados.
    """
    settings = get_settings()
    dsn = oracledb.makedsn(
        settings.oracle_host,
        settings.oracle_port,
        service_name=settings.oracle_service,
    )
    conn = oracledb.connect(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=dsn,
    )
    timeout_final = timeout_s if timeout_s is not None else settings.oracle_query_timeout_s
    conn.call_timeout = timeout_final * 1000
    return conn


def testar_conexao() -> bool:
    """SELECT 1 FROM DUAL para validar conectividade (usado no /health)."""
    conn = get_oracle_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM DUAL")
        row = cur.fetchone()
        return row is not None and row[0] == 1
    finally:
        conn.close()
