"""
Leitura das planilhas de apoio do CT2010 (PROCV):
  - 2 - Plano de Contas.xlsx  → PACOTE + DESCRIÇÃO DA CONTA
  - 3 - Centro de Custo.xlsx  → RESPONSÁVEL + DESCRIÇÃO CC + CUSTO/DESPESA

Caminho da pasta vem de settings.pasta_apoio (configurável no .env).
"""
from pathlib import Path

import pandas as pd

from app.config import get_settings


def _pasta_apoio() -> Path:
    # Lazy pra permitir que o .env mude sem reimportar o módulo.
    return Path(get_settings().pasta_apoio)


def carregar_plano_contas():
    caminho = _pasta_apoio() / "2 - Plano de Contas.xlsx"
    df = pd.read_excel(caminho, sheet_name=0)

    cod_protheus = df.iloc[:, 5].astype(str).str.strip()     # coluna F
    pacote = df.iloc[:, 9]                                    # coluna J (Pacote de Contas.1)
    conta = df.iloc[:, 12].astype(str).str.strip()            # coluna M
    desc_conta = df.iloc[:, 13]                               # coluna N

    mapa_pacote = dict(zip(cod_protheus, pacote))
    mapa_desc_conta = dict(zip(conta, desc_conta))
    return mapa_pacote, mapa_desc_conta


def carregar_centro_custo():
    caminho = _pasta_apoio() / "3 - Centro de Custo.xlsx"
    df = pd.read_excel(caminho, sheet_name=0)

    cc = df.iloc[:, 0].astype(str).str.strip()   # coluna A
    responsavel = df.iloc[:, 9]                   # coluna J
    descricao = df.iloc[:, 1]                     # coluna B
    custo_despesa = df.iloc[:, 8]                 # coluna I

    mapa_responsavel = dict(zip(cc, responsavel))
    mapa_descricao = dict(zip(cc, descricao))
    mapa_custo_despesa = dict(zip(cc, custo_despesa))
    return mapa_responsavel, mapa_descricao, mapa_custo_despesa
