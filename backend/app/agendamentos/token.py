"""
Tokens de API para o script sincronizador do PC do usuário.

Formato do token em claro (visto só uma vez na criação):

    sk_ag_<id_agendamento>_<32_chars_random>

O prefixo `sk_ag_<id>_` facilita 2 coisas:
  - identificar na UI ("sk_ag_42_8f3d...")
  - descobrir rapidinho de qual agendamento é no backend (sem bcrypt scan)

Armazenamento: só o hash bcrypt do token no banco (coluna token_hash).

Verificação: dado um token na request, extraímos o id do agendamento do
prefixo, buscamos a linha, comparamos o bcrypt. Match → OK, miss → 401.
"""
from __future__ import annotations

import re
import secrets
from typing import Optional

import bcrypt

from app.models.agendamento import Agendamento


TOKEN_PREFIXO_FIXO = "sk_ag"
TOKEN_RE = re.compile(r"^sk_ag_(\d+)_([A-Za-z0-9_-]{16,})$")


def gerar_token(agendamento_id: int) -> tuple[str, str, str]:
    """
    Gera um token novo pra um agendamento recém-criado.

    Retorna (token_claro, token_hash, token_prefixo).
    O caller salva hash + prefixo no banco, mostra o claro UMA vez pro usuário.
    """
    rand = secrets.token_urlsafe(24)   # ~32 chars
    token_claro = f"{TOKEN_PREFIXO_FIXO}_{agendamento_id}_{rand}"
    token_hash = bcrypt.hashpw(token_claro.encode(), bcrypt.gensalt()).decode()
    # Prefixo exibido na UI: sk_ag_<id>_<primeiros 4 chars>
    token_prefixo = f"{TOKEN_PREFIXO_FIXO}_{agendamento_id}_{rand[:4]}"
    return token_claro, token_hash, token_prefixo


def extrair_id_do_token(token: str) -> Optional[int]:
    """Lê o id do agendamento a partir do prefixo. None se formato inválido."""
    m = TOKEN_RE.match(token.strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def token_bate(token_claro: str, ag: Agendamento) -> bool:
    """Compara o token em claro com o hash guardado no agendamento."""
    if not ag.token_hash:
        return False
    try:
        return bcrypt.checkpw(token_claro.encode(), ag.token_hash.encode())
    except Exception:
        return False
