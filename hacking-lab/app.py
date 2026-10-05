"""
HACKING LAB - TryHackMe Style Vulnerable Site
For educational purposes ONLY - Lab environment
Offensive + Defensive perspectives

Features:
- Hidden links (robots.txt, comments, sitemap, .git)
- Admin panel with IP blocking
- SQLi, XSS, LFI, IDOR, File Upload, Command Injection
- Defense dashboard

Run: python3 app.py
Then: http://localhost:5000
"""

from flask import Flask, request, render_template, redirect, url_for, session, make_response, jsonify, send_from_directory
import os
import sqlite3
import time
from datetime import datetime
import hashlib
import re
from functools import wraps

app = Flask(__name__)
app.secret_key = 'lab_secret_key_for_education_only_123'

# In-memory storage for demo
BLOCKED_IPS = set()
ATTEMPT_LOG = []
USERS = {
    'admin': {'password': 'admin123', 'role': 'admin', 'id': 1},
    'alice': {'password': 'alice123', 'role': 'user', 'id': 2},
    'bob': {'password': 'bob123', 'role': 'user', 'id': 3},
    'guest': {'password': 'guest', 'role': 'guest', 'id': 4}
}
COMMENTS = [
    {"user": "alice", "comment": "Great site! <script>alert('XSS test')</script>", "time": "2024-01-01"},
    {"user": "bob", "comment": "Check /admin_backup maybe?", "time": "2024-01-02"}
]
FILES = {
    '1': {'owner': 'alice', 'name': 'alice_private.txt', 'content': 'Alice secret: THM{alice_secret_123}'},
    '2': {'owner': 'bob', 'name': 'bob_notes.txt', 'content': 'Bob secret: THM{bob_secret_456}'},
    '3': {'owner': 'admin', 'name': 'flag.txt', 'content': 'FLAG: THM{admin_flag_you_found_hidden_panel}'}
}

def log_attempt(ip, path, method, payload="", blocked=False):
    entry = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip': ip,
        'path': path,
        'method': method,
        'payload': str(payload)[:200],
        'blocked': blocked
    }
    ATTEMPT_LOG.insert(0, entry)
    if len(ATTEMPT_LOG) > 100:
        ATTEMPT_LOG.pop()

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)

def is_blocked(ip):
    return ip in BLOCKED_IPS

@app.before_request
def check_blocked():
    ip = get_ip()
    # Don't block defense and static
    if request.path.startswith('/defense') or request.path.startswith('/static'):
        return
    if is_blocked(ip):
        log_attempt(ip, request.path, request.method, "BLOCKED", blocked=True)
        return f"<h1>IP Blocked</h1><p>Your IP {ip} is blocked. Contact admin.</p><p>Defensive: This is IP blocking in action. Go to /defense to unblock (admin only)</p>", 403

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or USERS.get(session['user'], {}).get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# --- ROUTES ---

@app.route('/')
def index():
    ip = get_ip()
    log_attempt(ip, '/', 'GET')
    return render_template('index.html', ip=ip)

@app.route('/robots.txt')
def robots():
    # Hidden links - first recon step
    return """User-agent: *
Disallow: /admin
Disallow: /admin_backup
Disallow: /hidden
Disallow: /secret_notes.txt
Disallow: /backup.zip
Disallow: /.git/
# TODO: remove /dev panel - /dev_console
# Admin panel moved to /admin_panel_v2
"""

@app.route('/sitemap.xml')
def sitemap():
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>/</loc></url>
  <url><loc>/login</loc></url>
  <url><loc>/dashboard</loc></url>
  <url><loc>/search</loc></url>
  <url><loc>/profile</loc></url>
  <url><loc>/hidden</loc></url>
  <url><loc>/admin</loc></url>
  <!-- hidden: /api/users , /dev_console , /backup -->
</urlset>
"""

@app.route('/secret_notes.txt')
def secret_notes():
    return """Developer notes:
- admin password is still admin123, need to change
- backup at /admin_backup - contains old admin panel
- hidden API at /api/users?id=1 - IDOR vulnerability for testing
- TODO: fix SQLi in /login and /search
- TODO: fix XSS in /comments
- Secret flag in /hidden_flag_92j3k.txt
- .git exposed at /.git/ - need to block
"""

@app.route('/hidden_flag_92j3k.txt')
def hidden_flag():
    return "THM{hidden_file_found_via_robots}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    ip = get_ip()
    error = ""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        log_attempt(ip, '/login', 'POST', f"user={username}")

        # VULNERABLE: SQL Injection - directly concatenates
        # Try: admin' --  or  ' OR '1'='1
        # Defense: Use parameterized queries
        conn = sqlite3.connect(':memory:')
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (id INT, user TEXT, pass TEXT)")
        c.execute("DELETE FROM users")
        for u, d in USERS.items():
            c.execute("INSERT INTO users VALUES (?, ?, ?)", (d['id'], u, d['password']))
        # VULNERABLE QUERY
        query = f"SELECT * FROM users WHERE user='{username}' AND pass='{password}'"
        try:
            c.execute(query)
            result = c.fetchone()
            if result:
                session['user'] = result[1]
                session['user_id'] = result[0]
                return redirect(url_for('dashboard'))
            else:
                error = f"Invalid login. Query: {query}"
        except Exception as e:
            error = f"SQL Error: {e} | Query: {query}"

    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    ip = get_ip()
    log_attempt(ip, '/dashboard', 'GET')
    return render_template('dashboard.html', user=session['user'], users=USERS, role=USERS[session['user']]['role'])

@app.route('/search')
def search():
    # VULNERABLE: SQLi + XSS
    q = request.args.get('q', '')
    ip = get_ip()
    log_attempt(ip, '/search', 'GET', q)
    # Simulate SQLi
    result = f"Searching for: {q}"
    if "' OR" in q or "' --" in q or "admin" in q.lower():
        result += f"<br><br>SQLi Detected! Would return: admin, alice, bob<br>Query: SELECT * FROM products WHERE name LIKE '%{q}%'"
    # VULNERABLE: Reflected XSS - directly renders q without escaping (we mark safe in template for demo)
    return render_template('search.html', q=q, result=result)

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    # VULNERABLE: IDOR - ?id=1 can access other users
    user_id = request.args.get('id', str(session.get('user_id', '')))
    ip = get_ip()
    log_attempt(ip, f'/profile?id={user_id}', 'GET')
    # Find user by id
    target = None
    for u, d in USERS.items():
        if str(d['id']) == str(user_id):
            target = u
            break
    if not target:
        target = session['user']
    # VULNERABLE: IDOR - no check if target == session user
    return render_template('profile.html', user=target, data=USERS.get(target), requested_id=user_id, current_user=session['user'])

@app.route('/files')
def files():
    if 'user' not in session:
        return redirect(url_for('login'))
    # VULNERABLE: IDOR for files
    file_id = request.args.get('id', '1')
    ip = get_ip()
    log_attempt(ip, f'/files?id={file_id}', 'GET')
    f = FILES.get(file_id)
    if f:
        # No ownership check - IDOR
        return render_template('files.html', file=f, file_id=file_id, all_files=FILES)
    return "File not found", 404

@app.route('/comments', methods=['GET', 'POST'])
def comments():
    ip = get_ip()
    if request.method == 'POST':
        comment = request.form.get('comment', '')
        log_attempt(ip, '/comments', 'POST', comment)
        # VULNERABLE: Stored XSS - saves without sanitizing
        COMMENTS.append({"user": session.get('user', 'anon'), "comment": comment, "time": datetime.now().strftime('%Y-%m-%d')})
    
    return render_template('comments.html', comments=COMMENTS)

@app.route('/admin')
@app.route('/admin_panel_v2')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))
    if USERS.get(session['user'], {}).get('role') != 'admin':
        return "Access Denied - Admin only. Your IP logged.", 403
    ip = get_ip()
    log_attempt(ip, '/admin', 'GET')
    return render_template('admin.html', users=USERS, blocked=BLOCKED_IPS, logs=ATTEMPT_LOG[:20], flag=FILES['3']['content'])

@app.route('/admin_backup')
def admin_backup():
    # Hidden backup - recon finding
    return """
    <h1>Admin Backup 2023</h1>
    <!-- Old admin creds: admin / admin123 -->
    <!-- Backup flag: THM{backup_found} -->
    <a href="/admin">Admin Panel</a><br>
    <a href="/dev_console">Dev Console</a>
    """

@app.route('/hidden')
def hidden():
    # Page with hidden links in comments and invisible divs
    return render_template('hidden.html')

@app.route('/dev_console')
def dev_console():
    # VULNERABLE: Command Injection + LFI
    cmd = request.args.get('cmd', '')
    file = request.args.get('file', '')
    ip = get_ip()
    log_attempt(ip, f'/dev_console?cmd={cmd}&file={file}', 'GET')
    output = ""
    if cmd:
        # VULNERABLE: Command Injection
        # Try: cmd=whoami or cmd=cat /etc/passwd
        if re.search(r'[;&|`$]', cmd):
            output = f"Command injection detected! Would execute: {cmd}<br>Simulated output: root, admin, etc"
        else:
            output = f"Executed: {cmd} (blocked special chars in secure version)"
    if file:
        # VULNERABLE: LFI
        # Try: file=../../../../etc/passwd or file=secret_notes.txt
        output += f"<br>LFI attempt: {file}<br>"
        if "passwd" in file or "secret" in file or "flag" in file:
            output += f"File content would be: THM{{lfi_found_{file}}}"
    
    return render_template('dev_console.html', output=output, cmd=cmd, file=file)

@app.route('/api/users')
def api_users():
    # VULNERABLE: IDOR API
    user_id = request.args.get('id', '1')
    ip = get_ip()
    log_attempt(ip, f'/api/users?id={user_id}', 'GET')
    for u, d in USERS.items():
        if str(d['id']) == user_id:
            return jsonify({"id": d['id'], "username": u, "role": d['role'], "password": d['password']})
    return jsonify({"error": "User not found"}), 404

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # VULNERABLE: File upload bypass
    msg = ""
    if request.method == 'POST':
        f = request.files.get('file')
        if f:
            filename = f.filename
            ip = get_ip()
            log_attempt(ip, '/upload', 'POST', filename)
            # VULNERABLE: Only checks extension, not content
            if filename.endswith('.php') or filename.endswith('.phtml'):
                msg = f"Blocked .php upload (secure). Bypass with .php5 or double extension: {filename}.jpg.php"
            else:
                msg = f"File {filename} uploaded to /uploads/{filename} - If it was .php, you'd get RCE! Flag: THM{{upload_bypass}}"
    return render_template('upload.html', msg=msg)

@app.route('/defense')
def defense():
    # DEFENSIVE perspective
    return render_template('defense.html', blocked=BLOCKED_IPS, logs=ATTEMPT_LOG, users=USERS)

@app.route('/defense/block', methods=['POST'])
def defense_block():
    if 'user' not in session or USERS.get(session['user'], {}).get('role') != 'admin':
        return "Admin only", 403
    ip_to_block = request.form.get('ip', '')
    if ip_to_block:
        BLOCKED_IPS.add(ip_to_block)
        log_attempt(get_ip(), f'/defense/block ip={ip_to_block}', 'POST', f"Blocked {ip_to_block}")
    return redirect(url_for('defense'))

@app.route('/defense/unblock', methods=['POST'])
def defense_unblock():
    if 'user' not in session or USERS.get(session['user'], {}).get('role') != 'admin':
        return "Admin only", 403
    ip_to_unblock = request.form.get('ip', '')
    BLOCKED_IPS.discard(ip_to_unblock)
    return redirect(url_for('defense'))

@app.route('/defense/clear_logs', methods=['POST'])
@admin_required
def clear_logs():
    ATTEMPT_LOG.clear()
    return redirect(url_for('defense'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Hidden .git
@app.route('/.git/config')
def git_config():
    return """[core]
repositoryformatversion = 0
[remote "origin"]
url = https://github.com/company/secret-project.git
# Flag: THM{git_exposed}
"""

@app.route('/backup.zip')
def backup_zip():
    return "Fake backup zip - contains source code. In real attack, you'd download and find creds. Flag: THM{backup_zip_found}"

if __name__ == '__main__':
    print("""
============================================
  HACKING LAB - Educational Use Only
  Offensive + Defensive
  http://localhost:5000
  Admin: admin / admin123
============================================
  TryHackMe Style Rooms included:
  1. Recon: /robots.txt, /sitemap.xml, /secret_notes.txt, /.git/, comments
  2. Auth Bypass: SQLi in /login -> ' OR '1'='1
  3. IDOR: /profile?id=1, /files?id=3, /api/users?id=1
  4. XSS: /search?q=<script>alert(1)</script>, /comments stored XSS
  5. LFI: /dev_console?file=../../../../etc/passwd
  6. Command Injection: /dev_console?cmd=whoami
  7. File Upload: /upload bypass .php
  8. Admin: /admin, /admin_backup, /dev_console
  9. Defense: /defense - block IPs, view logs
============================================
    """)
    app.run(host='0.0.0.0', port=5000, debug=True)
