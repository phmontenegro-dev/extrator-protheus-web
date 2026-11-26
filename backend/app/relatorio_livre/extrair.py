"""
Extração dinâmica para o Relatório Livre.

Nome da tabela, colunas e campo de data são interpolados diretamente no SQL
(bind variables não funcionam para identificadores). Para manter isso seguro,
aplicamos defesa em profundidade:

  - a tabela é validada contra listar_tabelas() (dicionário do Oracle);
  - o campo_data (se informado) é validado contra listar_colunas(tabela);
  - as colunas selecionadas também são validadas contra listar_colunas(tabela);
  - filtros_extra (Etapa 12) têm nome de coluna validado e operador validado
    contra o tipo da coluna — ver app/relatorio_livre/filtros.py.

Se algum item vier fora dessas fontes controladas, a extração falha antes
de tocar o banco. Valores sempre vão como bind variables.
"""
from typing import List, Optional

import pandas as pd

from app.oracle import get_oracle_connection
from app.relatorio_livre.consulta_colunas import listar_colunas, listar_tabelas
from app.relatorio_livre.filtros import montar_where
from app.schemas.relatorio_livre import FiltroCampo


def extrair(
    tabela: str,
    colunas: List[str],
    campo_data: Optional[str],
    data_inicio: Optional[str],
    data_fim: Optional[str],
    max_linhas: Optional[int] = None,
    filtros_extra: Optional[List[FiltroCampo]] = None,
) -> pd.DataFrame:
    """
    Extração crua, sem tratamento adicional.

    Parâmetros:
        tabela: nome da tabela (uppercase). Validada contra listar_tabelas().
        colunas: lista de colunas. Todas validadas contra listar_colunas(tabela).
        campo_data: coluna usada no BETWEEN. None = sem filtro de data.
        data_inicio, data_fim: AAAAMMDD. Obrigatórias se campo_data informado.
        max_linhas: se informado, aplica ROWNUM <= max_linhas.
        filtros_extra: lista de FiltroCampo (Etapa 12 — filtros dinâmicos).
    """
    tabela = tabela.upper()

    tabelas_validas = set(listar_tabelas())
    if tabela not in tabelas_validas:
        raise ValueError(
            f"Tabela '{tabela}' não existe ou não é visível ao usuário do banco."
        )

    if not colunas:
        raise ValueError("Nenhuma coluna selecionada para a extração.")

    # Colunas: dict {nome: tipo_logico} pra usar no builder de filtros, e set
    # dos nomes pra validações rápidas.
    colunas_meta = {c["nome"]: c["tipo_logico"] for c in listar_colunas(tabela)}
    nomes_validos = set(colunas_meta.keys())

    invalidas = [c for c in colunas if c not in nomes_validos]
    if invalidas:
        raise ValueError(f"Colunas inválidas para {tabela}: {invalidas}")

    where_partes: list[str] = []
    params: dict = {}
    if campo_data:
        if campo_data not in nomes_validos:
            raise ValueError(f"Campo de data '{campo_data}' não existe em {tabela}.")
        if not data_inicio or not data_fim:
            raise ValueError("Datas obrigatórias quando o campo de data é informado.")
        where_partes.append(f"{campo_data} BETWEEN :data_inicio AND :data_fim")
        params["data_inicio"] = data_inicio
        params["data_fim"] = data_fim

    # Filtros dinâmicos (Etapa 12)
    if filtros_extra:
        frag, binds = montar_where(filtros_extra, colunas_meta)
        if frag:
            where_partes.append(frag)
            params.update(binds)

    if max_linhas is not None:
        if not isinstance(max_linhas, int) or max_linhas <= 0:
            raise ValueError("max_linhas deve ser um inteiro positivo.")
        where_partes.append(f"ROWNUM <= {max_linhas}")

    where_sql = f"WHERE {' AND '.join(where_partes)}" if where_partes else ""

    colunas_sql = ", ".join(colunas)
    query = f"SELECT {colunas_sql} FROM {tabela} {where_sql}"

    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

    return df
