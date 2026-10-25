import os
import sys
from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from werkzeug.security import check_password_hash

os.environ.setdefault('APP_DB','sqlite')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app,database,init_db,seed_demo


@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'test-secret-only','DB_ENGINE':'sqlite','SQLITE_PATH':str(tmp_path/'test.db'),'DEMO_MODE':True})
    with app.app_context():
        init_db();seed_demo()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def token(client,path='/login'):
    html=client.get(path)
    field=BeautifulSoup(html.data,'html.parser').find('input',{'name':'csrf_token'})
    if field:
        return field['value']
    with client.session_transaction() as sess:
        return sess.get('_csrf','')


def post(client,path,data=None):
    with client.session_transaction() as sess:
        csrf=sess.get('_csrf')
    if not csrf:
        csrf=token(client)
    return client.post(path,data={'csrf_token':csrf,**(data or {})})


def login(client,name='user',password='CyberDeskUser!2026'):
    return post(client,'/login',{'username':name,'password':password})


def register(client,name='alice',password='LongPassword!2026',**extra):
    return post(client,'/register',{'username':name,'password':password,'confirm_password':password,**extra})


def test_public_and_hidden_reports(client):
    assert client.get('/').status_code==200
    assert client.get('/reports/1').status_code==200
    assert client.get('/reports/4').status_code==404
    assert 'Zbyt szczegółowy' not in client.get('/').text


def test_registration_hash_and_fixed_user_role(app,client):
    assert register(client,role='admin').status_code==302
    with app.app_context(),database() as db:
        user=db.one('SELECT * FROM users WHERE username=%s',('alice',))
    assert user['role']=='user'
    assert user['password']!='LongPassword!2026'
    assert check_password_hash(user['password'],'LongPassword!2026')
    assert login(client,'alice','LongPassword!2026').status_code==302


@pytest.mark.parametrize('name,password',[('aa','LongPassword!2026'),('bad name','LongPassword!2026'),('valid','short')])
def test_registration_validation(client,name,password):
    assert register(client,name,password).status_code==400


def test_duplicate_case_insensitive_registration(client):
    assert register(client,'Alice').status_code==302
    assert register(client,'ALICE').status_code==400


def test_missing_and_wrong_csrf(client):
    assert client.post('/login',data={'username':'user','password':'CyberDeskUser!2026'}).status_code==400
    token(client)
    assert client.post('/register',data={'csrf_token':'invalid'}).status_code==400
    assert client.post('/register',data={'csrf_token':'ąęć'}).status_code==400


def test_login_rotation_logout_and_cookie_flags(client):
    old=token(client)
    response=login(client)
    assert response.status_code==302
    with client.session_transaction() as sess:
        assert sess['user_id']
        assert sess['_csrf']!=old
        assert 'role' not in sess
    cookie=response.headers.get('Set-Cookie','')
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    assert client.get('/logout').status_code==405
    assert post(client,'/logout').status_code==302
    assert client.get('/my-reports').status_code==302


def test_login_rate_limit(app,client):
    for _ in range(5):
        assert login(client,password='wrong').status_code==401
    response=login(client)
    assert response.status_code==429 and int(response.headers['Retry-After'])>0
    with app.app_context(),database() as db:
        db.execute('UPDATE login_attempts SET blocked_until=0,last_attempt=0')
    assert login(client).status_code==302


def test_sql_injection_is_not_login(client):
    assert login(client,"' OR 1=1 --",'anything').status_code==401
    with client.session_transaction() as sess:
        assert not sess.get('user_id')


def test_create_and_view_own_pending(app,client):
    login(client)
    response=post(client,'/add_report',{'title':'Nowe zgłoszenie','description':'Wystarczająco dokładny opis problemu.','severity':'Wysoka','approved':'true','author':'admin','status':'Naprawione'})
    assert response.status_code==302
    path=response.headers['Location']
    assert client.get(path).status_code==200
    with app.app_context(),database() as db:
        report=db.one('SELECT * FROM reports ORDER BY id DESC LIMIT 1')
    assert report['author']=='user' and not report['approved'] and report['status']=='Nowe'
    assert 'Nowe zgłoszenie' in client.get('/my-reports').text
    table=BeautifulSoup(client.get('/').data,'html.parser').select_one('.reports-table')
    assert 'Nowe zgłoszenie' not in table.get_text()
    other=app.test_client()
    assert other.get(path).status_code==404


@pytest.mark.parametrize('data',[{'title':'','description':'Opis prawidłowej długości','severity':'Wysoka'}, {'title':'Test','description':'x','severity':'Niska'}, {'title':'Test','description':'Opis prawidłowej długości','severity':'Nieznana'}])
def test_report_server_validation(client,data):
    login(client)
    assert post(client,'/add_report',data).status_code==400


def test_user_cannot_edit_others_or_moderate(app,client):
    login(client)
    payload={'title':'Zmieniony tytuł','description':'Wystarczająco długi opis.','severity':'Niska'}
    assert client.get('/reports/1/edit').status_code==403
    assert post(client,'/reports/1/edit',payload).status_code==403
    for path in ['/approve/4','/delete/1','/reports/1/status']:
        assert post(client,path,{'status':'Naprawione'}).status_code==403
    assert client.get('/admin').status_code==403
    assert client.get('/admin/audit').status_code==403
    with app.app_context(),database() as db:
        assert db.one('SELECT title FROM reports WHERE id=1')['title']!='Zmieniony tytuł'


def test_hidden_report_no_access_by_id(app,client):
    register(client);login(client,'alice','LongPassword!2026')
    assert client.get('/reports/4').status_code==404
    assert post(client,'/comment/4',{'content':'Unauthorized'}).status_code==404
    assert client.get('/reports/4/edit').status_code==404


def test_edit_requires_reapproval(app,client):
    login(client)
    assert post(client,'/reports/2/edit',{'title':'Zaktualizowany tytuł','description':'Nowy opis o prawidłowej długości.','severity':'Średnia'}).status_code==302
    with app.app_context(),database() as db:
        report=db.one('SELECT * FROM reports WHERE id=2')
    assert not report['approved'] and report['status']=='Nowe'
    assert client.get('/reports/2').status_code==200
    assert 'Zaktualizowany tytuł' not in client.get('/').text


def test_admin_approval_status_edit_and_audit(app,client):
    login(client,'admin','CyberDeskAdmin!2026')
    assert client.get('/admin').status_code==200
    assert 'Zbyt szczegółowy' in client.get('/admin').text
    assert post(client,'/approve/4').status_code==302
    for status in ['W trakcie analizy','Naprawione']:
        assert post(client,'/reports/4/status',{'status':status}).status_code==302
    assert post(client,'/reports/4/status',{'status':'Wrong'}).status_code==400
    assert post(client,'/reports/4/edit',{'title':'Poprawiony przez admina','description':'Opis poprawiony przez administratora.','severity':'Niska'}).status_code==302
    with app.app_context(),database() as db:
        report=db.one('SELECT * FROM reports WHERE id=4')
    assert report['approved'] and report['status']=='Naprawione'
    assert 'Zmieniono status' in client.get('/admin/audit').text


def test_comments_escaping_authorization_and_cascade(app,client):
    login(client)
    payload='<script>alert("xss")</script>'
    assert post(client,'/comment/1',{'content':payload}).status_code==302
    page=client.get('/reports/1').text
    assert payload not in page and '&lt;script&gt;' in page
    with app.app_context(),database() as db:
        cid=db.one('SELECT id FROM comments ORDER BY id DESC LIMIT 1')['id']
    post(client,'/logout');register(client);login(client,'alice','LongPassword!2026')
    assert post(client,f'/comments/{cid}/delete').status_code==403
    post(client,'/logout');login(client,'admin','CyberDeskAdmin!2026')
    assert post(client,f'/comments/{cid}/delete').status_code==302
    assert post(client,'/delete/1').status_code==302
    with app.app_context(),database() as db:
        assert db.one('SELECT COUNT(*) AS n FROM comments WHERE report_id=1')['n']==0
        assert db.one("SELECT COUNT(*) AS n FROM audit_events WHERE event='Usunięto zgłoszenie'")['n']==1


def test_pending_cannot_be_commented_and_empty_rejected(client):
    login(client)
    assert post(client,'/comment/4',{'content':'Komentarz'}).status_code==403
    assert post(client,'/comment/1',{'content':'  '}).status_code==400


def test_stored_xss_in_title_and_description(app,client):
    login(client,'admin','CyberDeskAdmin!2026')
    response=post(client,'/add_report',{'title':'<img src=x onerror=alert(1)>','description':'<script>alert("xss")</script>','severity':'Krytyczna'})
    page=client.get(response.headers['Location']).text
    assert '<script>alert(' not in page and '<img src=x' not in page
    assert '&lt;script&gt;' in page and '&lt;img' in page


def test_filters_and_pagination(app,client):
    assert 'Nieprawidłowa kontrola' in client.get('/?severity=Krytyczna').text
    assert 'Brak ograniczenia' not in client.get('/?severity=Krytyczna').text
    assert 'Brak nagłówka' in client.get('/?status=Naprawione').text
    assert 'Brak ograniczenia' in client.get('/?q=logowania').text
    assert client.get('/?q=%27%20OR%201=1--').status_code==200
    with app.app_context(),database() as db:
        for n in range(12):
            db.execute("INSERT INTO reports (author,title,description,severity,approved) VALUES ('admin',%s,'Opis testowy','Niska',TRUE)",(f'Pagination {n}',))
    assert 'strona 1 z 2' in client.get('/').text
    assert 'strona 2 z 2' in client.get('/?page=2').text
    assert client.get('/?page=abc').status_code==200


def test_sessions_cannot_supply_admin_role(app,client):
    login(client)
    with client.session_transaction() as sess:
        sess['role']='admin'
    assert client.get('/admin').status_code==403
    # Revocation in the database takes effect on the next request.
    with app.app_context(),database() as db:
        db.execute("UPDATE users SET role='admin' WHERE username='user'")
    assert client.get('/admin').status_code==200


def test_headers_error_pages_and_post_csrf(app,client):
    response=client.get('/')
    for header in ['Content-Security-Policy','X-Content-Type-Options','X-Frame-Options','Referrer-Policy']:
        assert header in response.headers
    assert response.headers['Cache-Control']=='no-store'
    assert client.get('/missing').status_code==404
    assert client.get('/health').json=={'status':'ok'}
    login(client,'admin','CyberDeskAdmin!2026')
    for path in ['/approve/4','/delete/1','/reports/1/status','/comment/1','/logout']:
        assert client.post(path,data={}).status_code==400


def test_idempotent_database_init(app):
    with app.app_context():
        init_db();init_db();seed_demo()
        with database() as db:
            assert db.one('SELECT COUNT(*) AS n FROM users')['n']==2
            assert db.one('SELECT COUNT(*) AS n FROM reports')['n']==4
