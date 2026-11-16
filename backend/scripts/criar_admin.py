"""
Script CLI para criar o primeiro usuário admin (ou promover/redefinir
senha de um usuário existente).

Uso:
    cd backend
    source .venv/bin/activate
    python scripts/criar_admin.py

Senha nunca aceita via argumento — sempre perguntada interativamente
(com confirmação) e nunca ecoada na tela.

Comportamento quando o usuário já existe:
    - Pergunta se quer promover a admin e/ou redefinir a senha.
"""
import argparse
import getpass
import sys
from pathlib import Path

# Garante que `app.*` seja importável, independente do cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.password import SenhaInvalidaError, gerar_hash  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402


def _pedir_senha() -> str:
    """Pede senha + confirmação, valida política. Repete até dar certo."""
    while True:
        s1 = getpass.getpass("Senha (mín. 8 chars + 1 caractere especial): ")
        s2 = getpass.getpass("Confirme a senha: ")
        if s1 != s2:
            print("  >> As senhas não conferem. Tente novamente.\n")
            continue
        try:
            hash_senha = gerar_hash(s1)
            return hash_senha
        except SenhaInvalidaError as e:
            print(f"  >> {e}\n")


def _confirmar(pergunta: str) -> bool:
    resp = input(f"{pergunta} [s/N]: ").strip().lower()
    return resp in {"s", "sim", "y", "yes"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Criar/atualizar usuário admin.")
    ap.add_argument("--username", help="Username. Se omitido, é perguntado.")
    ap.add_argument("--nome", help="Nome completo. Se omitido, é perguntado.")
    ap.add_argument("--email", help="Email (opcional).")
    args = ap.parse_args()

    username = (args.username or input("Username: ").strip()).lower()
    if not username:
        print("ERRO: username vazio.")
        return 1

    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.username == username).first()

        if existente is not None:
            print(f"\nUsuário '{username}' já existe:")
            print(f"  nome:    {existente.nome_completo}")
            print(f"  admin:   {existente.is_admin}")
            print(f"  ativo:   {existente.ativo}")

            promover = (not existente.is_admin) and _confirmar(
                "Promover a admin?"
            )
            resetar = _confirmar("Redefinir senha?")

            if not (promover or resetar):
                print("Nada a fazer.")
                return 0

            if promover:
                existente.is_admin = True
                existente.ativo = True
                print("  >> Promovido a admin (e reativado se inativo).")

            if resetar:
                existente.senha_hash = _pedir_senha()
                print("  >> Senha redefinida.")

            db.commit()
            return 0

        # Novo usuário
        nome = args.nome or input("Nome completo: ").strip()
        if not nome:
            print("ERRO: nome vazio.")
            return 1
        email = (args.email or input("Email (opcional, enter para pular): ").strip()) or None

        hash_senha = _pedir_senha()

        novo = Usuario(
            username=username,
            nome_completo=nome,
            email=email,
            senha_hash=hash_senha,
            is_admin=True,
            ativo=True,
        )
        db.add(novo)
        db.commit()

        print(f"\nUsuário admin '{username}' criado com sucesso.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
