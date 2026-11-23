"""
Infraestrutura de auto-descoberta de relatórios prontos (Etapa 11.6).

Cada relatório pronto exporta um objeto `relatorio = RelatorioPronto(...)`
no `__init__.py` do seu pacote (ou no próprio módulo, se for arquivo único).
O loader varre `app.relatorios_prontos.*` no startup, coleta todos os
`relatorio` e monta o registro em memória.

A partir daí:
  - `/relatorios` lista lê do registro
  - `/relatorios/{id}/extrair` é 1 endpoint genérico que despacha pelo id
  - `runner_relatorio_pronto(id, ...)` também lê do registro

Zero edição em outros arquivos ao adicionar um relatório novo.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from typing import Callable, Dict, Literal, Optional

import pandas as pd

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Tipos
# -----------------------------------------------------------------------------

TipoFiltro = Literal["nenhum", "periodo", "filial_periodo"]
# Nota: "livre" e "sql" ficam de fora do auto-descoberta — eles têm rotas
# próprias e não cabem no modelo "SELECT + tratar DataFrame".

ExtrairFn = Callable[..., pd.DataFrame]
TratarFn = Optional[Callable[[pd.DataFrame], pd.DataFrame]]


@dataclass(frozen=True)
class RelatorioPronto:
    """
    Metadados + funções de um relatório pronto.

    `extrair` é chamado com **kwargs — todos os filtros do payload chegam
    como keyword arguments (data_inicio, data_fim, filial...). Em um
    relatório sem filtros, declare-o assim pra ignorar o que vier:

        def extrair(**_) -> pd.DataFrame: ...

    Pra relatórios com filtros, use os argumentos nomeados e deixe **_ no
    fim como safety net:

        def extrair(data_inicio: str, data_fim: str, **_) -> pd.DataFrame: ...
    """
    id: str
    nome: str
    descricao: str
    filtros: TipoFiltro
    extrair: ExtrairFn
    tratar: TratarFn = None
    # Opcional. Se None, o padrão é f"{ID.upper()}_{data_inicio}_a_{data_fim}.csv"
    # (ou apenas f"{ID.upper()}.csv" quando filtros="nenhum"). Use quando quiser
    # um nome bonito tipo "CT2010_tratado_...".
    nome_arquivo_template: Optional[str] = None

    def nome_arquivo(self, filtros_validados: dict) -> str:
        """
        Monta o nome do CSV baseado no template (se definido) ou no padrão.
        `filtros_validados` traz as chaves data_inicio, data_fim, filial
        já em formato Protheus (YYYYMMDD / string pura).
        """
        if self.nome_arquivo_template:
            try:
                return self.nome_arquivo_template.format(**filtros_validados)
            except KeyError as e:
                log.warning("template de nome falhou (%s) em %s — usando padrão", e, self.id)

        base = self.id.upper()
        if self.filtros == "periodo":
            di = filtros_validados.get("data_inicio", "")
            df = filtros_validados.get("data_fim", "")
            return f"{base}_{di}_a_{df}.csv"
        if self.filtros == "filial_periodo":
            fil = filtros_validados.get("filial", "")
            di = filtros_validados.get("data_inicio", "")
            df = filtros_validados.get("data_fim", "")
            return f"{base}_{fil}_{di}_a_{df}.csv"
        return f"{base}.csv"


# -----------------------------------------------------------------------------
# Registro global
# -----------------------------------------------------------------------------

_REGISTRO: Optional[Dict[str, RelatorioPronto]] = None


def descobrir_relatorios(forcar: bool = False) -> Dict[str, RelatorioPronto]:
    """
    Varre `app.relatorios_prontos.*` e monta o registro `{id: RelatorioPronto}`.

    Ignora módulos que começam com `_` (incluindo `_loader`), além de
    `base`, `registry` e módulos auxiliares que não exportem `relatorio`.

    O resultado é cacheado em memória após a primeira chamada. Use
    `forcar=True` em testes pra reaplicar a varredura.
    """
    global _REGISTRO
    if _REGISTRO is not None and not forcar:
        return _REGISTRO

    import app.relatorios_prontos as pkg

    descobertos: Dict[str, RelatorioPronto] = {}

    # iter_modules pega tanto .py quanto subpackages, no nível direto de
    # relatorios_prontos/. Isso suporta os 2 formatos descritos no doc:
    #   - relatorios_prontos/sa1_clientes.py  (simples)
    #   - relatorios_prontos/ct2010/          (com __init__.py + apoio.py etc)
    for info in pkgutil.iter_modules(pkg.__path__):
        nome_mod = info.name
        # Pula convenções internas:
        if nome_mod.startswith("_") or nome_mod in {"base", "registry"}:
            continue

        caminho = f"app.relatorios_prontos.{nome_mod}"
        try:
            mod = importlib.import_module(caminho)
        except Exception:
            log.exception("falha ao importar %s — ignorando", caminho)
            continue

        rel = getattr(mod, "relatorio", None)
        if not isinstance(rel, RelatorioPronto):
            # Módulo auxiliar (ex: ct2010.apoio não passaria aqui porque é
            # submódulo de um subpackage, não módulo top-level) — ignora
            # silenciosamente.
            continue

        if rel.id in descobertos:
            raise RuntimeError(
                f"conflito: 2 relatórios declaram id={rel.id!r} "
                f"(módulos: {nome_mod} e o anterior)"
            )
        descobertos[rel.id] = rel
        log.debug("relatório descoberto: %s (%s)", rel.id, rel.filtros)

    _REGISTRO = descobertos
    log.info("auto-descoberta: %d relatórios registrados", len(descobertos))
    return _REGISTRO


def buscar_registro(id: str) -> Optional[RelatorioPronto]:
    return descobrir_relatorios().get(id)


def listar_registro() -> list[RelatorioPronto]:
    return list(descobrir_relatorios().values())
