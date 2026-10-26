import os
import secrets
from pathlib import Path

path = Path(__file__).resolve().parent / '.env'
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Plik .env już istnieje — usuń go, aby wygenerować nowe hasła (ADMIN i APP).')
else:
    with os.fdopen(fd, 'w') as handle:
        handle.write(
            f'SECRET_KEY={secrets.token_hex(32)}\n'
            f'ADMIN_DB_PASS={secrets.token_urlsafe(32)}\n'
            f'APP_DB_PASS={secrets.token_urlsafe(32)}\n'
            'DEMO_MODE=1\nCOOKIE_SECURE=0\n'
        )
    print('Utworzono konfigurację. Uruchom: docker compose up --build')
