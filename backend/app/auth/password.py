"""
Hash de senhas (bcrypt) e validação da política mínima.

Política: 8+ caracteres, pelo menos 1 caractere especial.

Caractere especial = qualquer coisa que não seja letra ou dígito. Lista
explícita evita ambiguidade (ex.: acento conta ou não?).
"""
import string

from passlib.context import CryptContext


# bcrypt é o padrão sólido para hash de senha. Rounds no default (12).
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Conjunto de caracteres considerados "especiais" para a política.
CARACTERES_ESPECIAIS = set(string.punctuation)  # !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~
SENHA_MIN_CHARS = 8


class SenhaInvalidaError(ValueError):
    """Lança quando a senha não atende à política."""
    pass


def validar_politica(senha: str) -> None:
    """
    Verifica a política mínima. Lança SenhaInvalidaError com mensagem
    descritiva quando não atende.
    """
    if len(senha) < SENHA_MIN_CHARS:
        raise SenhaInvalidaError(
            f"Senha deve ter pelo menos {SENHA_MIN_CHARS} caracteres."
        )
    if not any(c in CARACTERES_ESPECIAIS for c in senha):
        raise SenhaInvalidaError(
            "Senha deve ter pelo menos um caractere especial "
            "(ex.: !@#$%&*()-_=+.,)."
        )


def gerar_hash(senha: str) -> str:
    """Gera o hash bcrypt da senha (após validar a política)."""
    validar_politica(senha)
    return _pwd.hash(senha)


def verificar(senha: str, hash_armazenado: str) -> bool:
    """True se a senha bate com o hash. False em qualquer outra situação."""
    try:
        return _pwd.verify(senha, hash_armazenado)
    except Exception:
        # Hash corrompido/inválido etc — trata como senha errada.
        return False
