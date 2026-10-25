"""CyberDesk: Flask/PostgreSQL, with explicit SQLite preview/test mode."""
import functools
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import click
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
SEVERITIES = ('Niska', 'Średnia', 'Wysoka', 'Krytyczna')
STATUSES = ('Nowe', 'W trakcie analizy', 'Naprawione')


class Database:
    def __init__(self, conn, local=False):
        self.conn, self.local = conn, local

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        # Only developer-authored SQL; user values always remain bound parameters.
        cur.execute(sql.replace('%s', '?') if self.local else sql, params)
        return cur

    def one(self, sql, params=()):
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql, params=()):
        return [dict(row) for row in self.execute(sql, params).fetchall()]


@contextmanager
def database():
    local = current_app.config['DB_ENGINE'] == 'sqlite'
    if local:
        conn = sqlite3.connect(current_app.config['SQLITE_PATH'], timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
    else:
        options = dict(cursor_factory=RealDictCursor, connect_timeout=10, options='-c timezone=UTC')
        if current_app.config['DATABASE_URL']:
            conn = psycopg2.connect(current_app.config['DATABASE_URL'], **options)
        else:
            conn = psycopg2.connect(host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'vulntrack'), user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASS', ''), **options)
    try:
        yield Database(conn, local)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with database() as db:
        if not db.local:
            # Upgrade the original ZIP's schema without discarding data.
            db.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password TEXT NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'user')")
            db.execute('ALTER TABLE users ALTER COLUMN password TYPE TEXT')
            db.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            db.execute("CREATE TABLE IF NOT EXISTS reports (id SERIAL PRIMARY KEY, author VARCHAR(50) NOT NULL, title VARCHAR(150) NOT NULL, description TEXT NOT NULL, severity VARCHAR(20) NOT NULL, approved BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            db.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'Nowe'")
            db.execute('ALTER TABLE reports ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        schema = (ROOT / 'init.sql').read_text()
        if db.local:
            schema = schema.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        for statement in schema.split(';'):
            if statement.strip():
                db.execute(statement)
        for user in db.all('SELECT id, password FROM users'):
            if not user['password'].startswith(('scrypt:', 'pbkdf2:')):
                db.execute('UPDATE users SET password=%s WHERE id=%s', (generate_password_hash(user['password']), user['id']))


def seed_demo():
    with database() as db:
        for name, password, role in [('admin', 'CyberDeskAdmin!2026', 'admin'), ('user', 'CyberDeskUser!2026', 'user')]:
            db.execute('INSERT INTO users (username,password,role) VALUES (%s,%s,%s) ON CONFLICT (username) DO NOTHING', (name,generate_password_hash(password),role))
        if db.one('SELECT COUNT(*) AS n FROM reports')['n']:
            return
        examples = [
            ('admin','Nieprawidłowa kontrola dostępu do faktur','Zmiana identyfikatora faktury w adresie pozwala odczytać dokument innego użytkownika.\n\nKroki odtworzenia:\n1. Zaloguj się na konto testowe.\n2. Otwórz własną fakturę.\n3. Zmień identyfikator na dokument drugiego konta testowego.\n\nOczekiwane zachowanie: odpowiedź 403 lub 404. Test wykonano w środowisku laboratoryjnym.','Krytyczna','W trakcie analizy',True),
            ('user','Brak ograniczenia prób logowania w panelu testowym','Panel testowanej aplikacji pozwala wielokrotnie wysyłać błędne hasło bez czasowej blokady. Należy wprowadzić limit prób i rejestrowanie nieudanych logowań.','Wysoka','Nowe',True),
            ('admin','Brak nagłówka X-Content-Type-Options','Odpowiedzi serwera nie zawierały nagłówka nosniff. Dodano go w konfiguracji serwera i potwierdzono jego obecność w odpowiedziach.','Niska','Naprawione',True),
            ('user','Zbyt szczegółowy komunikat błędu API','Niepoprawny parametr powoduje wyświetlenie wewnętrznej ścieżki pliku. Zamiast szczegółów implementacji użytkownik powinien otrzymywać ogólny komunikat błędu.','Średnia','Nowe',False),
        ]
        for author,title,description,severity,status,approved in examples:
            db.execute('INSERT INTO reports (author,title,description,severity,status,approved) VALUES (%s,%s,%s,%s,%s,%s)', (author,title,description,severity,status,approved))
        rid = db.one('SELECT id FROM reports ORDER BY id LIMIT 1')['id']
        db.execute('INSERT INTO comments (report_id,author,content) VALUES (%s,%s,%s)', (rid,'user','Potwierdzam w środowisku testowym. Problem dotyczy również eksportu dokumentu do PDF.'))


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash('Zaloguj się, aby wykonać tę czynność.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def is_admin():
    return bool(g.user and g.user['role'] == 'admin')


def admin_required(view):
    @login_required
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def visible_report(db, rid):
    report = db.one('SELECT * FROM reports WHERE id=%s', (rid,))
    if not report or not (report['approved'] or is_admin() or (g.user and report['author'] == g.user['username'])):
        abort(404)
    return report


def audit(db, event, rid=None, detail=''):
    db.execute('INSERT INTO audit_events (actor,event,report_id,detail) VALUES (%s,%s,%s,%s)', (g.user['username'],event,rid,detail))


def report_values():
    title, description = request.form.get('title','').strip(), request.form.get('description','').strip()
    severity = request.form.get('severity','')
    if not 3 <= len(title) <= 150:
        return None, 'Tytuł musi mieć od 3 do 150 znaków.'
    if not 10 <= len(description) <= 10000:
        return None, 'Opis musi mieć od 10 do 10 000 znaków.'
    if severity not in SEVERITIES:
        return None, 'Wybierz prawidłowy poziom zagrożenia.'
    return (title,description,severity), None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), DB_ENGINE=os.environ.get('APP_DB','postgres'),
        SQLITE_PATH=os.environ.get('SQLITE_PATH',str(ROOT/'instance'/'preview.db')), DATABASE_URL=os.environ.get('DATABASE_URL'),
        DEMO_MODE=os.environ.get('DEMO_MODE')=='1', SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE')=='1', PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=65536)
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY']:
        instance = ROOT/'instance'; instance.mkdir(exist_ok=True, mode=0o700)
        keyfile = instance/'.session-key'
        try:
            with keyfile.open('x') as handle:
                os.chmod(keyfile,0o600); handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = keyfile.read_text().strip()

    @app.before_request
    def protect_request():
        g.user = None
        if request.endpoint in ('static','health'):
            return
        if request.method == 'POST':
            token, expected = request.form.get('csrf_token',''), session.get('_csrf','')
            if not expected or not hmac.compare_digest(expected.encode(),token.encode()):
                abort(400, description='Formularz wygasł lub brakuje tokenu CSRF. Odśwież stronę i spróbuj ponownie.')
        if session.get('user_id'):
            with database() as db:
                g.user = db.one('SELECT id,username,role FROM users WHERE id=%s',(session['user_id'],))
            if not g.user:
                session.clear()

    @app.after_request
    def security_headers(response):
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'SAMEORIGIN','Referrer-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'self'; style-src 'self'; img-src 'self' data:; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"})
        if request.endpoint != 'static':
            response.headers['Cache-Control']='no-store'
        if request.is_secure:
            response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.context_processor
    def context():
        return dict(csrf_token=csrf_token,severities=SEVERITIES,statuses=STATUSES,admin=is_admin(),demo=app.config['DEMO_MODE'])

    @app.template_filter('shortdate')
    def shortdate(value):
        if not value:
            return '—'
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(ZoneInfo('Europe/Warsaw')).strftime('%Y-%m-%d %H:%M')

    app.add_template_filter(lambda value: dict(zip(SEVERITIES,('low','medium','high','critical'))).get(value,'low'),'severity_class')
    app.add_template_filter(lambda value: dict(zip(STATUSES,('new','analysis','fixed'))).get(value,'new'),'status_class')

    @app.get('/health')
    def health():
        try:
            with database() as db:
                db.one('SELECT 1 AS ok')
            return {'status':'ok'}
        except (psycopg2.Error,sqlite3.Error):
            return {'status':'unavailable'},503

    def listing(scope):
        conditions, params = [],[]
        if scope=='mine':
            conditions.append('r.author=%s'); params.append(g.user['username'])
        elif scope=='admin':
            moderation=request.args.get('moderation','pending')
            if moderation in ('pending','approved'):
                conditions.append('r.approved=%s'); params.append(moderation=='approved')
        else:
            conditions.append('r.approved=TRUE')
        q=request.args.get('q','').strip()[:150]
        if q:
            conditions.append('(LOWER(r.title) LIKE LOWER(%s) OR LOWER(r.description) LIKE LOWER(%s))'); params.extend([f'%{q}%',f'%{q}%'])
        for name,choices in [('severity',SEVERITIES),('status',STATUSES)]:
            value=request.args.get(name,'')
            if value in choices:
                conditions.append('r.'+name+'=%s'); params.append(value)
        where=' AND '.join(conditions) or '1=1'
        page=max(1,request.args.get('page',1,type=int))
        with database() as db:
            total=db.one('SELECT COUNT(*) AS n FROM reports r WHERE '+where,params)['n']
            pages=max(1,(total+9)//10); page=min(page,pages)
            reports=db.all('SELECT r.*, (SELECT COUNT(*) FROM comments c WHERE c.report_id=r.id) AS comment_count FROM reports r WHERE '+where+' ORDER BY r.created_at DESC,r.id DESC LIMIT %s OFFSET %s',params+[10,(page-1)*10])
            stats=db.one("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN status <> 'Naprawione' THEN 1 ELSE 0 END),0) AS active, COALESCE(SUM(CASE WHEN status = 'Naprawione' THEN 1 ELSE 0 END),0) AS fixed, COALESCE(SUM(CASE WHEN severity = 'Krytyczna' AND status <> 'Naprawione' THEN 1 ELSE 0 END),0) AS critical FROM reports WHERE approved=TRUE")
            pending=db.one('SELECT COUNT(*) AS n FROM reports WHERE approved=FALSE')['n'] if is_admin() else None
        def page_url(n):
            args=request.args.to_dict(); args['page']=n
            return url_for(request.endpoint,**args)
        return render_template('index.html',scope=scope,reports=reports,stats=stats,pending=pending,total=total,page=page,pages=pages,page_url=page_url)

    @app.get('/')
    def index():
        return listing('all')

    @app.get('/my-reports')
    @login_required
    def my_reports():
        return listing('mine')

    @app.get('/admin')
    @admin_required
    def admin_panel():
        return listing('admin')

    @app.get('/admin/audit')
    @admin_required
    def audit_log():
        with database() as db:
            events=db.all('SELECT * FROM audit_events ORDER BY id DESC LIMIT 100')
        return render_template('audit.html',events=events)

    @app.route('/register',methods=['GET','POST'])
    def register():
        if g.user:
            return redirect(url_for('index'))
        if request.method=='POST':
            username=request.form.get('username','').strip().lower(); password=request.form.get('password','')
            error=None
            if not re.fullmatch(r'[a-z0-9_.-]{3,50}',username):
                error='Login: 3–50 znaków, litery bez polskich znaków, cyfry, kropka, myślnik lub podkreślenie.'
            elif not 10<=len(password)<=128:
                error='Hasło musi mieć od 10 do 128 znaków.'
            elif password!=request.form.get('confirm_password',''):
                error='Podane hasła nie są identyczne.'
            if not error:
                with database() as db:
                    cur=db.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,'user') ON CONFLICT DO NOTHING",(username,generate_password_hash(password)))
                    if not cur.rowcount:
                        error='Ten login jest już zajęty.'
                if not error:
                    flash('Konto zostało utworzone. Możesz się zalogować.','success'); return redirect(url_for('login'))
            flash(error,'danger'); return render_template('auth.html',mode='register'),400
        return render_template('auth.html',mode='register')

    dummy_hash=generate_password_hash(secrets.token_urlsafe(20))

    @app.route('/login',methods=['GET','POST'])
    def login():
        if g.user:
            return redirect(url_for('index'))
        if request.method=='POST':
            username=request.form.get('username','').strip().lower()[:50]; password=request.form.get('password','')
            now=int(time.time()); ip=request.remote_addr or 'unknown'
            buckets=[(hashlib.sha256(f'account:{ip}:{username}'.encode()).hexdigest(),5),(hashlib.sha256(f'ip:{ip}'.encode()).hexdigest(),30)]
            with database() as db:
                for key,limit in buckets:
                    attempt=db.one('SELECT * FROM login_attempts WHERE key=%s',(key,))
                    if attempt and attempt['blocked_until']>now:
                        flash('Za dużo nieudanych prób. Spróbuj ponownie za 15 minut.','danger')
                        response=app.make_response((render_template('auth.html',mode='login'),429))
                        response.headers['Retry-After']=str(attempt['blocked_until']-now); return response
                user=db.one('SELECT * FROM users WHERE LOWER(username)=%s',(username,))
                valid=len(password)<=128 and check_password_hash(user['password'] if user else dummy_hash,password)
                if not user or not valid:
                    for key,limit in buckets:
                        db.execute('INSERT INTO login_attempts (key,attempts,last_attempt,blocked_until) VALUES (%s,1,%s,0) ON CONFLICT (key) DO UPDATE SET attempts=CASE WHEN login_attempts.last_attempt < %s THEN 1 ELSE login_attempts.attempts+1 END,last_attempt=%s',(key,now,now-900,now))
                        db.execute('UPDATE login_attempts SET blocked_until=%s WHERE key=%s AND attempts >= %s',(now+900,key,limit))
                    flash('Błędny login lub hasło.','danger'); return render_template('auth.html',mode='login'),401
                db.execute('DELETE FROM login_attempts WHERE key=%s',(buckets[0][0],))
            session.clear(); session['user_id']=user['id']; session.permanent=True; csrf_token()
            flash('Zalogowano pomyślnie.','success'); return redirect(url_for('index'))
        return render_template('auth.html',mode='login')

    @app.post('/logout')
    def logout():
        session.clear(); flash('Wylogowano.','info'); return redirect(url_for('index'))

    @app.route('/add_report',methods=['GET','POST'])
    @login_required
    def add_report():
        if request.method=='POST':
            values,error=report_values()
            if error:
                flash(error,'danger'); return render_template('add_report.html',report=None),400
            with database() as db:
                report=db.one('INSERT INTO reports (author,title,description,severity,approved) VALUES (%s,%s,%s,%s,%s) RETURNING id',(g.user['username'],*values,is_admin()))
                audit(db,'Dodano zgłoszenie',report['id'])
            flash('Zgłoszenie opublikowano.' if is_admin() else 'Zgłoszenie zapisano. Czeka na akceptację administratora.','success')
            return redirect(url_for('report_detail',report_id=report['id']))
        return render_template('add_report.html',report=None)

    @app.get('/reports/<int:report_id>')
    def report_detail(report_id):
        with database() as db:
            report=visible_report(db,report_id)
            comments=db.all('SELECT * FROM comments WHERE report_id=%s ORDER BY created_at,id',(report_id,))
        can_edit=bool(g.user and (is_admin() or g.user['username']==report['author']))
        return render_template('report.html',report=report,comments=comments,can_edit=can_edit)

    @app.route('/reports/<int:report_id>/edit',methods=['GET','POST'])
    @login_required
    def edit_report(report_id):
        with database() as db:
            report=visible_report(db,report_id)
            if not is_admin() and report['author']!=g.user['username']:
                abort(403)
            if request.method=='POST':
                values,error=report_values()
                if error:
                    flash(error,'danger'); return render_template('add_report.html',report=report),400
                approved=bool(report['approved']) if is_admin() else False
                status=report['status'] if is_admin() else 'Nowe'
                db.execute('UPDATE reports SET title=%s,description=%s,severity=%s,approved=%s,status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s',(*values,approved,status,report_id))
                audit(db,'Edytowano zgłoszenie',report_id)
                flash('Zmiany zapisano.' if is_admin() else 'Zmiany zapisano. Zgłoszenie ponownie czeka na akceptację.','success')
                return redirect(url_for('report_detail',report_id=report_id))
        return render_template('add_report.html',report=report)

    @app.post('/approve/<int:report_id>')
    @admin_required
    def approve_report(report_id):
        with database() as db:
            visible_report(db,report_id)
            db.execute('UPDATE reports SET approved=TRUE,updated_at=CURRENT_TIMESTAMP WHERE id=%s',(report_id,))
            audit(db,'Zaakceptowano zgłoszenie',report_id)
        flash('Zgłoszenie zaakceptowano i opublikowano.','success')
        return redirect(url_for('report_detail',report_id=report_id))

    @app.post('/reports/<int:report_id>/status')
    @admin_required
    def change_status(report_id):
        status=request.form.get('status','')
        if status not in STATUSES:
            abort(400,description='Nieprawidłowy status.')
        with database() as db:
            report=visible_report(db,report_id)
            db.execute('UPDATE reports SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s',(status,report_id))
            audit(db,'Zmieniono status',report_id,f"{report['status']} → {status}")
        flash('Status zaktualizowano.','success'); return redirect(url_for('report_detail',report_id=report_id))

    @app.post('/delete/<int:report_id>')
    @admin_required
    def delete_report(report_id):
        with database() as db:
            report=visible_report(db,report_id)
            audit(db,'Usunięto zgłoszenie',report_id,report['title'])
            db.execute('DELETE FROM reports WHERE id=%s',(report_id,))
        flash('Zgłoszenie usunięto wraz z komentarzami.','info'); return redirect(url_for('admin_panel'))

    @app.post('/comment/<int:report_id>')
    @login_required
    def add_comment(report_id):
        content=request.form.get('content','').strip()
        with database() as db:
            report=visible_report(db,report_id)
            if not report['approved']:
                abort(403,description='Komentowanie jest dostępne po akceptacji zgłoszenia.')
            if not 1<=len(content)<=2000:
                abort(400,description='Komentarz musi mieć od 1 do 2000 znaków.')
            db.execute('INSERT INTO comments (report_id,author,content) VALUES (%s,%s,%s)',(report_id,g.user['username'],content))
            audit(db,'Dodano komentarz',report_id)
        flash('Komentarz dodano.','success'); return redirect(url_for('report_detail',report_id=report_id)+'#comments')

    @app.post('/comments/<int:comment_id>/delete')
    @login_required
    def delete_comment(comment_id):
        with database() as db:
            comment=db.one('SELECT * FROM comments WHERE id=%s',(comment_id,))
            if not comment:
                abort(404)
            visible_report(db,comment['report_id'])
            if not is_admin() and comment['author']!=g.user['username']:
                abort(403)
            db.execute('DELETE FROM comments WHERE id=%s',(comment_id,)); audit(db,'Usunięto komentarz',comment['report_id'])
        flash('Komentarz usunięto.','info'); return redirect(url_for('report_detail',report_id=comment['report_id'])+'#comments')

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages={403:'Nie masz uprawnień do tej operacji.',404:'Nie znaleziono zgłoszenia lub strony.',405:'Ta operacja wymaga formularza POST.',413:'Przesłany formularz jest zbyt duży.'}
        return render_template('error.html',code=error.code,message=messages.get(error.code,error.description)),error.code

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html',code=500,message='Wystąpił błąd serwera. Spróbuj ponownie później.'),500

    @app.cli.command('init-db')
    def init_command():
        init_db(); click.echo('Schemat bazy i migracja gotowe.')

    @app.cli.command('seed-demo')
    def seed_command():
        seed_demo(); click.echo('Dodano dane demonstracyjne. Dane logowania opisano w README.')

    @app.cli.command('create-admin')
    @click.argument('username')
    @click.password_option(confirmation_prompt=True)
    def admin_command(username,password):
        username=username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_.-]{3,50}',username) or not 10<=len(password)<=128:
            raise click.ClickException('Nieprawidłowy login lub długość hasła (10–128 znaków).')
        with database() as db:
            cur=db.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,'admin') ON CONFLICT DO NOTHING",(username,generate_password_hash(password)))
            if not cur.rowcount:
                raise click.ClickException('Login jest zajęty. Nie zmieniono istniejącego konta.')
        click.echo('Utworzono administratora.')

    return app


app=create_app()
if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
