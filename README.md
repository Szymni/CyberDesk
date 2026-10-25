# CyberDesk — platforma zgłaszania podatności

Pełna aplikacja Flask + PostgreSQL. Rozwija projekt z przesłanego ZIP-a. Oba pierwotne szablony pozostają w `templates/`; wspólny układ jest w `templates/base.html`. Frontend używa lokalnego Bootstrap 5.3.3 i własnego CSS. Nazwa interfejsu została ujednolicona do CyberDesk.

## Szybki start: Docker + PostgreSQL

Wymagania: Python 3.10+ do wygenerowania konfiguracji oraz uruchomiony Docker Desktop z Docker Compose.

W folderze projektu wykonaj:

```sh
python setup_local.py
docker compose up --build
```

Otwórz **http://localhost:5000**. Pierwsze uruchomienie wymaga pobrania obrazów i pakietów. Baza przechodzi kontrolę gotowości przed startem serwera. PostgreSQL nie ma opublikowanego portu, a aplikacja jest domyślnie dostępna tylko na komputerze lokalnym.

Skrypt `setup_local.py` generuje niezależne, losowe `SECRET_KEY` i `DB_PASS` w `.env`. Nie nadpisuje istniejącego pliku. Nie udostępniaj `.env` ani nie dodawaj go do repozytorium.

Domyślnie włączone jest lokalne demo (`DEMO_MODE=1`):

| Rola | Login | Hasło demonstracyjne |
|---|---|---|
| Administrator | `admin` | `CyberDeskAdmin!2026` |
| Użytkownik | `user` | `CyberDeskUser!2026` |

To publicznie opisane konta **wyłącznie do demonstracji**. Możesz zarejestrować nowe konto użytkownika. Rejestracja nie pozwala nadać sobie roli administratora. Przy istniejącej bazie seeder nie nadpisuje haseł ani danych.

Zatrzymanie aplikacji bez usuwania bazy:

```sh
docker compose down
```

Dane PostgreSQL pozostają w nazwanym wolumenie `pgdata`. `docker compose logs web` pokazuje logi. Endpoint `/health` sprawdza połączenie z bazą i zwraca 200 albo 503.

## Funkcjonalności

- Rejestracja, logowanie, wylogowanie przez POST i sesja z czasem ważności 2 godziny.
- Dodawanie podatności: tytuł, opis, poziom Niska / Średnia / Wysoka / Krytyczna.
- Lista opublikowanych zgłoszeń, szczegóły, wyszukiwanie, filtrowanie i stronicowanie.
- „Moje zgłoszenia”: również wpisy oczekujące na akceptację administratora.
- Edycja własnych wpisów. Edycja przez użytkownika cofa publikację do moderacji i ustawia status „Nowe”.
- Administrator może edytować i usuwać dowolne zgłoszenie, publikować wpisy oczekujące i zmieniać status: Nowe / W trakcie analizy / Naprawione.
- Komentarze do opublikowanych wpisów, usuwanie własnych komentarzy, moderacja wszystkich komentarzy przez administratora.
- Osobny panel moderacji z filtrami publikacji i dziennik ostatnich 100 działań.
- Responsywny interfejs, komunikaty walidacji, puste stany i strony błędów.
- Daty w interfejsie są wyświetlane w strefie Europe/Warsaw. Baza przechowuje czas UTC.

Akceptacja publikacji (`approved`) i status rozwiązania (`status`) to dwa niezależne pola. Zaakceptowane zgłoszenia są publicznie czytelne, zgodnie z pierwotnym działaniem aplikacji. Niezaakceptowane wpisy mogą odczytać tylko autor i administrator. Komentowanie niezaakceptowanych wpisów jest zablokowane.

## Zabezpieczenia

- Hasła są haszowane przez Werkzeug (scrypt), nie przechowywane jawnym tekstem.
- Token CSRF jest obowiązkowy we wszystkich formularzach POST, w tym logowaniu i rejestracji.
- Dane w SQL są przekazywane jako parametry. Filtry nie interpolują danych użytkownika do kodu SQL.
- Domyślne escapowanie Jinja obejmuje tytuły, opisy i komentarze. HTML użytkownika nie jest interpretowany.
- Własność wpisu i uprawnienia są sprawdzane w backendzie. Rola jest pobierana z bazy przy każdym żądaniu, a nie z pola przesłanego przez przeglądarkę.
- Przy logowaniu sesja i token CSRF są zastępowane. Cookies: HttpOnly, SameSite=Lax, czas ważności 2 godziny.
- Limit logowania: 5 błędnych prób dla pary adres IP + login albo 30 z tego samego IP; blokada 15 minut. Liczniki są w bazie, wspólne dla workerów. Nagłówki X-Forwarded-For od klienta nie są uznawane za wiarygodne.
- Walidacja po stronie serwera obejmuje długości, puste wartości, dozwolone poziomy zagrożenia i statusy; rozmiar żądania jest ograniczony.
- Nagłówki CSP, nosniff, SAMEORIGIN, same-origin; strony aplikacji mają Cache-Control: no-store.
- Debug jest wyłączony. Docker uruchamia Gunicorn jako użytkownik bez roota i z systemem plików tylko do odczytu.

Jeżeli aplikacja ma być udostępniona poza localhost: użyj HTTPS, ustaw `COOKIE_SECURE=1`, wyłącz `DEMO_MODE`, utwórz własnego administratora i skonfiguruj zaufany reverse proxy. HSTS jest dodawany, gdy Flask rozpoznaje połączenie jako HTTPS. Konfigurację proxy należy dopasować do faktycznej infrastruktury. Ten projekt nie włącza publicznego hostingu.

Aby uruchomić bez przykładowych kont, ustaw `DEMO_MODE=0` w `.env` **przed pierwszym startem**, a potem wykonaj:

```sh
docker compose run --rm web python -m flask --app app create-admin twojlogin
```

Hasło podasz w ukrytym, interaktywnym monicie. Wyłączenie DEMO_MODE nie usuwa kont utworzonych wcześniej; do środowiska produkcyjnego użyj nowej, pustej bazy.

## Istniejąca baza z pierwotnego projektu

`init-db` dodaje brakujące pola `status`, `updated_at`, `created_at` oraz tabele limitowania logowań i dziennika. Zamienia stare hasła na hasze bez zmiany wartości hasła. Nie usuwa zgłoszeń ani komentarzy. Przed migracją rzeczywistej bazy wykonaj kopię zapasową; konta z dawnymi hasłami testowymi wymagają zmiany. Nowy Compose korzysta z nowego nazwanego wolumenu, więc istniejący wolumen trzeba podłączyć i dopasować dane dostępowe świadomie.

## Lokalny podgląd bez Dockera

Podgląd uruchamia **ten sam backend Flask**, z jawnym wyborem SQLite zamiast PostgreSQL. Nie jest to atrapowy interfejs w JavaScript. Konta i zmiany zapisują się w `instance/preview.db`.

```sh
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python preview_server.py
```

Otwórz http://localhost:5000. Podgląd tworzy lokalny losowy klucz sesji w `instance/.session-key`. Nie należy kopiować go ani bazy podglądu do repozytorium. Podgląd automatycznie ładuje dane demonstracyjne do pustej bazy.

## Testy

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Testy tworzą własne, tymczasowe bazy SQLite. Obejmują rejestrację, haszowanie, limit logowania, rotację sesji, CSRF, próby SQL Injection i XSS, kontrolę cudzych wpisów, ukryte zgłoszenia, moderację, statusy, komentarze, kaskadowe usuwanie, ponowną akceptację po edycji i filtrowanie.

## Struktura

- `app.py` — backend, walidacja, migracja i komendy CLI.
- `templates/` — widoki Jinja.
- `static/` — CSS, JS, ikony i lokalny Bootstrap.
- `init.sql` — schemat bazy PostgreSQL, bez haseł i kont na sztywno.
- `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` — uruchomienie z PostgreSQL.
- `setup_local.py` — generator lokalnej konfiguracji.
- `preview_server.py` — uruchomienie demonstracyjne bez Dockera.
- `tests/` — testy funkcjonalności i zabezpieczeń.

Zakres weryfikacji wykonanej przy przygotowaniu paczki opisano w `VALIDATION.md`.
