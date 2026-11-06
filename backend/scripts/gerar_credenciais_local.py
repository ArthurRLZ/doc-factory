"""Cria credenciais novas para uma instalação local isolada, sem alterar credenciais existentes."""
import os
import secrets
from pathlib import Path


def main():
    pasta = Path.home() / ".docfactory"
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    destino = pasta / "credenciais.env"
    conteudo = "\n".join([
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}",
        f"JWT_SEGREDO={secrets.token_urlsafe(48)}",
        f"CPF_SEGREDO={secrets.token_urlsafe(48)}",
        "ADMIN_USUARIO=admin",
        f"ADMIN_SENHA={secrets.token_urlsafe(24)}",
        "",
    ])
    try:
        fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit("O arquivo já existe; nenhuma credencial foi alterada.") from None
    with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    print(f"Credenciais criadas em {destino}. Proteja o arquivo e faça uma cópia segura.")


if __name__ == "__main__":
    main()
