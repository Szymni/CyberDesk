# CyberDesk

Aplikacja do zgłaszania i śledzenia podatności, napisana we Flasku z bazą PostgreSQL. Frontend korzysta z HTML, CSS i Bootstrapa.

Użytkownicy mogą dodawać i edytować własne zgłoszenia oraz je komentować. Administrator zatwierdza wpisy, zmienia statusy i moderuje treści.

## Uruchomienie

Wymagania: Python 3.10+ oraz Docker z Compose.

```bash
python setup_local.py
docker compose up --build
```

Strona będzie dostępna pod http://localhost:5000.

Skrypt tworzy konfigurację w `.env`. Nie dodawaj tego pliku do repozytorium.


## Testy

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Testy korzystają z SQLite. Szczegóły weryfikacji są w [VALIDATION.md](VALIDATION.md).
