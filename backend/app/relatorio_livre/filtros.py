"""
Builder defensivo de WHERE pros filtros dinâmicos do Relatório Livre
(Etapa 12).

Regras duras:
  - O NOME da coluna é validado contra o dicionário Oracle antes de ir pro SQL
    (quem valida é o extrair.py — aqui assumimos coluna já válida).
  - O OPERADOR é escolhido de um enum restrito; combinações inválidas por
    tipo da coluna são rejeitadas.
  - Os VALORES vão sempre como bind variables (:p0, :p1, ...) — nunca
    interpolados no SQL.
  - Pra operadores sobre DATE, o valor ISO 'YYYY-MM-DD' vai pra TO_DATE no SQL.

A assinatura principal é `montar_where(filtros, colunas_info)` → devolve
`(fragmento_sql_sem_WHERE, dict_de_params)`. Lista vazia devolve ("", {}).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from app.schemas.relatorio_livre import (
    FiltroCampo,
    OPERADORES_POR_TIPO,
)


class FiltroInvalidoError(ValueError):
    """Qualquer problema de validação dos filtros vira isso.

    O router captura e devolve 422 pro cliente com mensagem clara.
    """


def montar_where(
    filtros: list[FiltroCampo],
    colunas_info: dict[str, str],
    prefixo_param: str = "f",
) -> tuple[str, dict[str, Any]]:
    """
    Dada uma lista de FiltroCampo e um dict {nome_coluna: tipo_logico},
    devolve (fragmento_SQL, params_bind).

    `fragmento_SQL` já vem com " AND " entre os termos, pronto pra ser
    concatenado por quem já tem um WHERE em construção. Lista vazia = ("", {}).
    """
    if not filtros:
        return "", {}

    termos: list[str] = []
    params: dict[str, Any] = {}
    idx = 0

    for f in filtros:
        tipo = colunas_info.get(f.coluna)
        if tipo is None:
            raise FiltroInvalidoError(
                f"Coluna '{f.coluna}' não existe na tabela escolhida."
            )
        operadores_validos = OPERADORES_POR_TIPO.get(tipo, set())
        if f.operador not in operadores_validos:
            raise FiltroInvalidoError(
                f"Operador '{f.operador}' não é válido pra coluna '{f.coluna}' "
                f"(tipo {tipo})."
            )

        sql, novos = _montar_termo(f, tipo, prefixo_param, idx)
        termos.append(sql)
        params.update(novos)
        idx += len(novos)

    return " AND ".join(f"({t})" for t in termos), params


# ---------------------------------------------------------------------------
# Um termo por filtro
# ---------------------------------------------------------------------------

def _montar_termo(
    f: FiltroCampo, tipo: str, prefixo: str, idx: int,
) -> tuple[str, dict[str, Any]]:
    """
    Gera o fragmento SQL + bind vars pra UM filtro. `idx` é o contador de
    params no builder, pra garantir nomes únicos sem colisão.
    """
    col = f.coluna  # já validado pelo chamador

    op = f.operador

    # ---- Operadores universais de nulidade ----
    if op == "is_null":
        return f"{col} IS NULL", {}
    if op == "nao_is_null":
        return f"{col} IS NOT NULL", {}

    # ---- Validação do valor por operador ----
    if op in ("entre", "data_entre"):
        if not isinstance(f.valor, list) or len(f.valor) != 2:
            raise FiltroInvalidoError(
                f"Operador '{op}' requer uma lista [min, max]."
            )
    elif op == "em_lista":
        if not isinstance(f.valor, list) or not f.valor:
            raise FiltroInvalidoError("Operador 'em_lista' requer uma lista não-vazia.")
    elif op == "ultimos_n_dias":
        if not isinstance(f.valor, (int, float)) or int(f.valor) < 0:
            raise FiltroInvalidoError("Operador 'ultimos_n_dias' requer um inteiro ≥ 0.")
    else:
        if f.valor is None or f.valor == "":
            raise FiltroInvalidoError(f"Operador '{op}' requer um valor.")

    # ---- Geração de SQL + binds ----
    p0 = f"{prefixo}{idx}"

    # ------ TEXTO ------
    if tipo == "texto":
        if op == "=":
            return f"{col} = :{p0}", {p0: str(f.valor)}
        if op == "<>":
            return f"{col} <> :{p0}", {p0: str(f.valor)}
        if op == "contem":
            # LIKE '%x%' — faz UPPER nos dois lados pra caseless
            return f"UPPER({col}) LIKE UPPER(:{p0})", {p0: f"%{f.valor}%"}
        if op == "comeca_com":
            return f"UPPER({col}) LIKE UPPER(:{p0})", {p0: f"{f.valor}%"}
        if op == "em_lista":
            # IN (:p0, :p1, ...) — expandido manualmente pra respeitar bind vars
            nomes = [f"{prefixo}{idx + i}" for i in range(len(f.valor))]
            placeholders = ", ".join(f":{n}" for n in nomes)
            binds = {n: str(v) for n, v in zip(nomes, f.valor)}
            return f"{col} IN ({placeholders})", binds

    # ------ NÚMERO ------
    if tipo == "numero":
        comps = {"=": "=", "<>": "<>", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        if op in comps:
            return f"{col} {comps[op]} :{p0}", {p0: _num(f.valor)}
        if op == "entre":
            p1 = f"{prefixo}{idx + 1}"
            lo, hi = f.valor
            return (
                f"{col} BETWEEN :{p0} AND :{p1}",
                {p0: _num(lo), p1: _num(hi)},
            )

    # ------ DATA (coluna DATE/TIMESTAMP do Oracle) ------
    if tipo == "data":
        if op == "data_igual":
            return f"TRUNC({col}) = TO_DATE(:{p0}, 'YYYY-MM-DD')", {p0: _data_iso(f.valor)}
        if op == "data_maior":
            return f"{col} > TO_DATE(:{p0}, 'YYYY-MM-DD')", {p0: _data_iso(f.valor)}
        if op == "data_menor":
            return f"{col} < TO_DATE(:{p0}, 'YYYY-MM-DD')", {p0: _data_iso(f.valor)}
        if op == "data_entre":
            p1 = f"{prefixo}{idx + 1}"
            lo, hi = f.valor
            return (
                f"{col} BETWEEN TO_DATE(:{p0}, 'YYYY-MM-DD') AND TO_DATE(:{p1}, 'YYYY-MM-DD')",
                {p0: _data_iso(lo), p1: _data_iso(hi)},
            )
        if op == "ultimos_n_dias":
            n = int(f.valor)
            # SYSDATE - N: últimos N dias até agora
            return f"{col} >= TRUNC(SYSDATE) - :{p0}", {p0: n}

    # Se chegou aqui, é bug — a validação do início já deveria pegar.
    raise FiltroInvalidoError(
        f"Combinação não implementada: tipo={tipo} operador={op}"
    )


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------

def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        raise FiltroInvalidoError(f"Valor '{x}' não é numérico.")


def _data_iso(x: Any) -> str:
    """
    Aceita 'YYYY-MM-DD', date ou datetime. Normaliza pra string ISO.
    """
    if isinstance(x, (date, datetime)):
        return x.strftime("%Y-%m-%d")
    s = str(x).strip()
    try:
        # valida o formato antes de mandar pro TO_DATE
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise FiltroInvalidoError(
            f"Data '{x}' não está em YYYY-MM-DD."
        )
