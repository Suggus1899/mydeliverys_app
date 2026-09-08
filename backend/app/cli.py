"""Comandos operativos sin endpoints publicos."""

import argparse
import asyncio
import getpass
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pyotp
from sqlalchemy import or_, select

from app.core.database import get_db_context
from app.core.security import encrypt_credential, hash_password, hash_recovery_code, normalize_phone
from app.models.user import RoleEnum, User


@dataclass(frozen=True)
class ProvisionAdminInput:
    email: str
    phone: str
    full_name: str
    password: str


async def provision_admin(data: ProvisionAdminInput) -> tuple[str, list[str]]:
    phone = normalize_phone(data.phone)
    email = data.email.strip().lower()
    if "@" not in email:
        raise ValueError("El correo no es valido.")
    if len(data.password) < 12:
        raise ValueError("La contrasena debe tener al menos 12 caracteres.")
    secret = pyotp.random_base32()
    recovery_codes = [secrets.token_hex(5).upper() for _ in range(8)]
    async with get_db_context() as db:
        exists = await db.scalar(
            select(User.id).where(or_(User.email == email, User.phone_number == phone))
        )
        if exists is not None:
            raise ValueError("Ya existe una cuenta con ese correo o telefono.")
        db.add(
            User(
                id=uuid4(),
                phone_number=phone,
                email=email,
                full_name=data.full_name.strip(),
                password_hash=hash_password(data.password),
                role=RoleEnum.SUPER_ADMIN,
                totp_secret_encrypted=encrypt_credential(secret),
                totp_recovery_hashes=[hash_recovery_code(code) for code in recovery_codes],
                totp_enabled_at=datetime.now(UTC),
            )
        )
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="MyDeliveryS")
    return uri, recovery_codes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision-admin", help="Provisiona el primer Super Admin")
    provision.add_argument("--email", required=True)
    provision.add_argument("--phone", required=True)
    provision.add_argument("--name", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "provision-admin":
        password = getpass.getpass("Contrasena: ")
        confirmation = getpass.getpass("Repite la contrasena: ")
        if password != confirmation:
            raise SystemExit("Las contrasenas no coinciden.")
        uri, recovery_codes = asyncio.run(
            provision_admin(
                ProvisionAdminInput(
                    email=args.email,
                    phone=args.phone,
                    full_name=args.name,
                    password=password,
                )
            )
        )
        print("Super Admin provisionado. Agrega esta URI a tu aplicacion TOTP:")
        print(uri)
        print("Codigos de recuperacion; guardalos una sola vez:")
        for code in recovery_codes:
            print(code)


if __name__ == "__main__":
    main()
