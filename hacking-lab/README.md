# HACKING LAB - TryHackMe Style (Educational)

**For lab practice only - Do not attack real sites**

## What is this?
A deliberately vulnerable website to practice:
- Finding hidden links (robots.txt, comments, .git, sitemap)
- Admin panel access
- Blocking IPs (defensive)
- SQLi, XSS, LFI, Command Injection, IDOR, File Upload

Both offensive and defensive perspectives included.

## Quick Start (Kali)

```bash
cd ~/hacking-lab
chmod +x start.sh
./start.sh
# Open http://localhost:5000
# Login: admin / admin123
```

## Structure (TryHackMe Rooms Inspired)

### Recon (Room: Web Fundamentals, Content Discovery)
- /robots.txt -> hidden paths
- /sitemap.xml -> hidden API
- /secret_notes.txt -> dev notes
- /.git/config -> git exposed
- /hidden -> invisible links, HTML comments
- View Source (Ctrl+U) everywhere

Flags: THM{hidden_file_found_via_robots}, THM{git_exposed}, THM{hidden_comments_found}

### Authentication Bypass (Room: OWASP Broken Auth)
- /login SQLi: username `admin' --` + any password
- Or `' OR '1'='1` in both fields
- Defense: parameterized queries

### IDOR (Room: Broken Access Control)
- /profile?id=1 -> change to 2,3 to see other users
- /files?id=1 -> id=3 gives admin flag
- /api/users?id=1 -> returns password
- Defense: check ownership

### XSS (Room: XSS)
- Reflected: /search?q=<script>alert(1)</script>
- Stored: /comments post <img src=x onerror=alert(1)>
- Defense: html.escape(), CSP

### LFI & Command Injection (Room: LFI, Command Injection)
- /dev_console?file=secret_notes.txt -> try ../../../../etc/passwd
- /dev_console?cmd=whoami -> try whoami;id
- Defense: whitelist, block ../ and ; & |

### File Upload (Room: File Upload Vulnerabilities)
- /upload -> bypass .php block with .php5, .jpg.php
- Defense: check MIME, rename, no exec

### Admin Panel & IP Blocking
- /admin_backup -> old creds -> /admin -> flag
- /defense -> Block IPs, view logs (Blue Team)
- Try to get blocked then bypass via X-Forwarded-For header

## Offensive Track (Red Team)

1. Recon: robots.txt, sitemap, secret_notes, .git, view source
2. Login bypass via SQLi
3. IDOR to get admin data
4. XSS to steal cookie
5. LFI to read flag
6. Command injection
7. Upload bypass
8. Find all THM{...} flags (10+)

## Defensive Track (Blue Team)

Go to /defense:
- See attacker IPs and payloads in logs
- Block IPs: add to BLOCKED set
- Unblock when false positive
- Learn secure code examples for each vuln
- Implement WAF rules

## TryHackMe Rooms to Study Alongside

- OWASP Top 10 (2021)
- Web Fundamentals
- Burp Suite Basics
- SQL Injection, XSS, LFI, Command Injection
- File Inclusion, SSRF, File Upload
- Jr Penetration Tester path

## Flags List (for testing)

- THM{hidden_file_found_via_robots}
- THM{git_exposed}
- THM{hidden_comments_found}
- THM{backup_found}
- THM{dashboard_admin_access}
- THM{idor_profile_admin}
- THM{admin_flag_you_found_hidden_panel}
- THM{lfi_found_...}
- THM{upload_bypass}
- THM{admin_panel_accessed}
- THM{backup_zip_found}
- etc (12 total)

## Warning

This is intentionally vulnerable. Never deploy to internet. Use only in your Kali lab VM.

## Separate from ANTAR

This lab is in ~/hacking-lab, ANTAR is in ~/ANTAR - completely separate.
ANTAR is for YouTube shorts, this is for hacking practice.
