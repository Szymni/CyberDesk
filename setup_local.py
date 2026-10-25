"""Generate local secrets without overwriting an existing configuration."""
import os
import secrets
from pathlib import Path
path = Path(__file__).resolve().parent / '.env'
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Plik .env już istnieje — pozostawiono bez zmian.')
else:
    with os.fdopen(fd, 'w') as handle:
        handle.write(f'SECRET_KEY={secrets.token_hex(32)}\nDB_PASS={secrets.token_urlsafe(32)}\nDEMO_MODE=1\n')
    print('Utworzono konfigurację. Uruchom: docker compose up --build')
