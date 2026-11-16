"""
Cadastro AMIGÁVEL de tabelas (opcional) para o Relatório Livre.

Este arquivo NÃO é uma whitelist obrigatória — o Relatório Livre lista
dinamicamente todas as tabelas visíveis ao usuário no dicionário do Oracle.

Para as tabelas cadastradas aqui, a tela:
  - Exibe a descrição amigável no dropdown (ex.: "CT2010 — Lançamentos Contábeis")
  - Pré-seleciona automaticamente o campo de data padrão
"""

# Regex para filtrar o dicionário Oracle. Pega tabelas do Protheus com padrão
# "letras + dígitos finais"; descarta tabelas do sistema (DUAL, ALL_TABLES, ...).
# Exemplos aceitos: SB1010, CT2010, QPR010, SFT010, ZAA010, MATA010.
# Em None, lista TODAS as tabelas visíveis ao usuário do banco.
FILTRO_NOMES_TABELAS = r"^[A-Z][A-Z0-9]{2,5}\d{3}$"


TABELAS_CONHECIDAS: dict[str, dict[str, str]] = {
    "CT2010": {
        "descricao": "CT2010  —  Lançamentos Contábeis",
        "campo_data": "CT2_DATA",
    },
    "QPR010": {
        "descricao": "QPR010  —  Medições de Qualidade",
        "campo_data": "QPR_DTMEDI",
    },
    "SFT010": {
        "descricao": "SFT010  —  Documentos de Entrada e Saída",
        "campo_data": "FT_ENTRADA",
    },
    "SD3010": {
        "descricao": "SD3010  —  Movimentações Internas",
        "campo_data": "D3_EMISSAO",
    },
}
