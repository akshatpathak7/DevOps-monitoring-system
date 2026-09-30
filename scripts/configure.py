"""Generate local configuration. Never overwrites an existing .env."""

import argparse
import base64
import getpass
import hashlib
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--demo", action="store_true", help="Use a documented local-only demo password"
)
args = parser.parse_args()
path = Path(__file__).resolve().parents[1] / ".env"
if path.exists():
    raise SystemExit(
        ".env already exists; edit it directly or move it before regenerating"
    )
password = (
    "ThemistoDemo2026!"
    if args.demo
    else getpass.getpass("Choose admin password (12+ characters): ")
)
if len(password) < 12:
    raise SystemExit("Use at least 12 characters")
salt = secrets.token_hex(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000)
encoded = f"pbkdf2_sha256$600000${salt}${base64.b64encode(digest).decode()}"
values = {
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD_HASH": encoded,
    "SESSION_SECRET": secrets.token_hex(32),
    "INGEST_TOKEN": secrets.token_hex(32),
    "DEMO_CONTROL_TOKEN": secrets.token_hex(32),
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-4o-mini",
    "PUBLIC_ORIGIN": "http://localhost:8080",
    "COOKIE_SECURE": "false",
    "SITE_ADDRESS": ":80",
}
# Single quotes prevent Compose from interpolating dollar signs in password hashes.
with path.open("x") as f:
    path.chmod(0o600)
    f.write("".join(f"{key}='{value}'\n" for key, value in values.items()))
print("Created .env with random internal credentials.")
if args.demo:
    print(
        "Local demo login: admin / ThemistoDemo2026! (choose a new password before public deployment)"
    )
