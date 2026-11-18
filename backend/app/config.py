"""
Configurações carregadas do .env, validadas via Pydantic.

Qualquer parte do código que precisa de credencial/URL deve importar daqui,
nunca ler os.environ direto — assim toda configuração passa pela validação
e fica tipada.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env fica na raiz do backend, um nível acima deste arquivo (app/).
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Ambiente
    env: str = "development"

    # PostgreSQL
    postgres_url: str

    # Oracle Protheus
    oracle_host: str
    oracle_port: int = 1521
    oracle_service: str
    oracle_user: str
    oracle_password: str

    # Segurança
    secret_key: str

    # CORS (lista separada por vírgula no .env)
    cors_origins: str = ""

    # Pasta com planilhas de apoio (PROCV do CT2010).
    # Caminho absoluto. Pode mudar no .env sem alterar código.
    pasta_apoio: str = "/opt/extrator-protheus/ExtratorProtheus/tb_APOIO"

    # Timeout (em segundos) para queries Oracle. Relatórios grandes podem
    # demorar — ajuste no .env se necessário.
    oracle_query_timeout_s: int = 600

    # ----- Jobs assíncronos (Etapa 11) -----
    # Onde ficam os CSVs dos jobs concluídos. A pasta precisa ser gravável
    # pelo usuário que roda o uvicorn (extrator, em produção).
    pasta_jobs: str = "/var/lib/extrator/jobs"
    # Workers rodando em paralelo. 2 é o padrão — protege Oracle e disco.
    jobs_max_workers: int = 2
    # Quantos jobs um usuário pode ter rodando OU na fila ao mesmo tempo.
    jobs_max_por_usuario: int = 1
    # Dias de retenção; passado isso o cronjob apaga o CSV e a linha do banco.
    jobs_retencao_dias: int = 1

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cache para carregar o .env uma única vez por processo."""
    return Settings()  # type: ignore[call-arg]
