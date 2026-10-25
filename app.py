import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'super_tajny_klucz_devsecops'

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'vulntrack'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASS', 'password'),
        cursor_factory=RealDictCursor
    )

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Pobranie zaakceptowanych postów
    cur.execute("SELECT * FROM reports WHERE approved = TRUE ORDER BY created_at DESC")
    approved_reports = cur.fetchall()
    
    # Pobranie oczekujących postów (tylko dla admina)
    pending_reports = []
    if session.get('role') == 'admin':
        cur.execute("SELECT * FROM reports WHERE approved = FALSE ORDER BY created_at DESC")
        pending_reports = cur.fetchall()
        
    # Pobranie komentarzy i przypisanie ich do postów
    cur.execute("SELECT * FROM comments ORDER BY created_at ASC")
    all_comments = cur.fetchall()
    
    comments_by_report = {}
    for c in all_comments:
        comments_by_report.setdefault(c['report_id'], []).append(c)
        
    cur.close()
    conn.close()
    
    return render_template(
        'index.html', 
        reports=approved_reports, 
        pending_reports=pending_reports, 
        comments=comments_by_report,
        login_page=False
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Zalogowano pomyślnie!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Błędny login lub hasło!', 'danger')
            
    return render_template('index.html', login_page=True)

@app.route('/logout')
def logout():
    session.clear()
    flash('Wylogowano.', 'info')
    return redirect(url_for('index'))

@app.route('/add_report', methods=['GET', 'POST'])
def add_report():
    if 'username' not in session:
        flash('Musisz być zalogowany, aby dodać post.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        severity = request.form['severity']
        
        # Posty admina są akceptowane automatycznie, użytkownika czekają na akceptację
        is_approved = True if session.get('role') == 'admin' else False
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reports (author, title, description, severity, approved) VALUES (%s, %s, %s, %s, %s)",
            (session['username'], title, description, severity, is_approved)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        if is_approved:
            flash('Post został dodany i opublikowany.', 'success')
        else:
            flash('Post został dodany i oczekuje na akceptację administratora.', 'info')
            
        return redirect(url_for('index'))
        
    return render_template('add_report.html')

@app.route('/approve/<int:report_id>', methods=['POST'])
def approve_report(report_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE reports SET approved = TRUE WHERE id = %s", (report_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Post został zaakceptowany!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Post został usunięty.', 'secondary')
    return redirect(url_for('index'))

@app.route('/comment/<int:report_id>', methods=['POST'])
def add_comment(report_id):
    if 'username' not in session:
        flash('Zaloguj się, aby skomentować.', 'warning')
        return redirect(url_for('login'))
        
    content = request.form['content']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO comments (report_id, author, content) VALUES (%s, %s, %s)",
        (report_id, session['username'], content)
    )
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Dodano komentarz.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)