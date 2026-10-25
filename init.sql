CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL
);

CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    author VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    author VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Konta użytkowników
INSERT INTO users (username, password, role) VALUES ('admin', 'admin', 'admin');
INSERT INTO users (username, password, role) VALUES ('user', 'user', 'user');

-- Przykładowe posty (jeden zaakceptowany, jeden oczekujący)
INSERT INTO reports (author, title, description, severity, approved) 
VALUES ('admin', 'Podatność SQL Injection w logowaniu', 'Brak filtracji znaków specjalnych w formularzu.', 'Krytyczna', TRUE);

INSERT INTO reports (author, title, description, severity, approved) 
VALUES ('user', 'Brak limitu prób logowania (Brute Force)', 'Można bez końca zgadywać hasło użytkownika.', 'Średnia', FALSE);

-- Przykładowy komentarz
INSERT INTO comments (report_id, author, content) 
VALUES (1, 'user', 'Potwierdzam, u mnie też występuje ten błąd.');