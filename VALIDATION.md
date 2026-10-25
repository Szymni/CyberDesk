# Weryfikacja L2

Sprawdzono lokalnie na tymczasowej bazie SQLite: strony główne, rejestrację, logowanie, moje zgłoszenia, dodawanie, edycję, panel administratora, akceptację, zmianę statusu, komentarze i filtry. Te scenariusze zakończyły się powodzeniem.

Potwierdzono zakres laboratoryjny: hasła zapisują się jawnie, formularze działają bez CSRF, nie ma blokady po błędnych logowaniach ani kontroli właściciela w endpointzie edycji. Brak dziennika zmian i tabel audytu oraz limitowania logowania. SQL pozostaje parametryzowany, a Jinja escapuje tekst jak w pierwotnym projekcie.

Nie uruchamiano kontenerów Docker ani PostgreSQL w tym środowisku. Nie dołączono zestawu 25 testów z późniejszego etapu; opisane sprawdzenie było kontrolą działania przed oddaniem paczki.
