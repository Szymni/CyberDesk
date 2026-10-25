# Weryfikacja — 25 października 2026

## Wynik

- 25 testów funkcjonalnych i zabezpieczeń zakończonych powodzeniem na tymczasowych bazach SQLite.
- Rzeczywista aplikacja Flask została uruchomiona w środowisku podglądu z SQLite i przykładowymi danymi.
- W przeglądarce sprawdzono listę zgłoszeń, filtrowanie poziomu zagrożenia, przejście do szczegółów i wyświetlenie komentarzy.
- Sprawdzono odpowiedzi HTTP stron głównej, logowania, rejestracji, szczegółów, zasobów statycznych oraz endpointu gotowości.
- Bootstrap jest dołączony lokalnie, więc wygląd nie wymaga połączenia z CDN.

## Testowane scenariusze

Rejestracja z walidacją i unikalnością loginu, próba nadania sobie roli administratora, przechowywanie haszy, logowanie i limit błędnych prób, rotacja sesji i CSRF, wylogowanie przez POST, odrzucanie brakującego lub nieprawidłowego CSRF, próba SQL Injection w logowaniu i wyszukiwaniu, escapowanie XSS w tytułach/opisach/komentarzach, tworzenie zgłoszeń oczekujących, dostęp autora do własnych ukrytych wpisów, blokada dostępu innych użytkowników, blokada edycji cudzych wpisów, kontrola roli dla wszystkich operacji administracyjnych, odczyt roli z bazy, ponowna moderacja po edycji, akceptacja, zmiana statusu, dziennik zmian, moderacja komentarzy i kaskadowe usuwanie. Testy potwierdzają również filtrowanie, stronicowanie i możliwość ponownego uruchomienia inicjalizacji bez duplikowania danych.

## Granice weryfikacji

W środowisku przygotowania projektu Docker nie jest zainstalowany, dlatego **nie wykonano `docker compose up` i nie zweryfikowano działających kontenerów PostgreSQL/Gunicorn**. Próba uruchomienia lokalnego PostgreSQL bez Dockera również zatrzymała się na ograniczeniach środowiska dotyczących tworzenia użytkownika systemowego. Kod adaptera PostgreSQL i migracji jest przygotowany; jego działanie na prawdziwym PostgreSQL pozostaje do sprawdzenia po uruchomieniu paczki w Dockerze. Podgląd SQLite nie stanowi takiego testu.

Testy są ukierunkowane na wskazane wymagania i podstawowe zabezpieczenia. Nie zastępują pełnego audytu ani konfiguracji środowiska produkcyjnego.
