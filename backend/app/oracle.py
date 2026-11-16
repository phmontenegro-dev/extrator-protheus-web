"""
Conexão com o Oracle Protheus (somente leitura).

Mesmo padrão do desktop — credenciais vêm do .env via config.Settings.
Agora com call_timeout aplicado (em milissegundos): queries que ultrapassam
o timeout são abortadas, evitando que uma consulta travada prenda recursos.
"""
import oracledb

from app.config import get_settings


def get_oracle_connection():
    """
    Abre uma conexão nova com o Oracle Protheus e aplica call_timeout.

    Importante: o call_timeout é em milissegundos. Cada chamada ao banco
    (execute, fetch) respeita esse limite individualmente.
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
    # Timeout por chamada (ms). Default: 10 minutos.
    conn.call_timeout = settings.oracle_query_timeout_s * 1000
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
