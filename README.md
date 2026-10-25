# CyberDesk - L2

Wersja deweloperska do lokalnego laboratorium. Flask, PostgreSQL, HTML/CSS i Bootstrap.

Rejestracja i logowanie, dodawanie oraz edycja zgłoszeń, statusy, komentarze, moderacja, wyszukiwarka i filtry.

## Uruchomienie

```sh
python setup_local.py
docker compose up --build
```

Otwórz http://localhost:5000. W Dockerze uruchamia się serwer deweloperski Flaska. Baza ma trwały wolumen i kontrolę gotowości.

Podgląd bez Dockera: zainstaluj requirements.txt i uruchom `python preview_server.py` (SQLite).

## Zakres L2

Celowo brak haszowania haseł, tokenów CSRF, limitu logowania, kontroli właściciela w endpointzie edycji i dziennika zmian. Te elementy są do wykonania na L7. Pozostają podstawowe logowanie i role dla panelu administratora. Zapytania parametryzowane i domyślne escapowanie Jinja pozostają jak w pierwotnym projekcie.

Nie ma Gunicorna, pipeline CI/CD ani dołączonego zestawu 25 testów z późniejszej wersji. Nie dodano celowo nowych podatności SQL Injection ani XSS. Debugger pozostaje wyłączony.

To aplikacja celowo niezabezpieczona, tylko na localhost, z fikcyjnymi danymi. Nie używaj prawdziwych haseł i nie wystawiaj jej do internetu. Konta demo są opisane na lokalnej stronie logowania.

Wolumen `pgdata_l2` jest osobny. Baza i hasze z poprzedniej wersji nie są nadpisywane; starych haszy nie da się zamienić z powrotem na hasła. W L2 konta zakłada się od nowa.

Wynik sprawdzenia: VALIDATION.md.
