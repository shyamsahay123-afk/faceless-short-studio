import sqlite3
import os

DB_NAME = 'shorts.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Channels Table
    c.execute('''CREATE TABLE IF NOT EXISTS channels (  
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        channel_name TEXT, 
        niche TEXT,   
        subscribers TEXT, 
        total_shorts INTEGER DEFAULT 0,
        youtube_credentials TEXT
    )''')  
      
    # Shorts Table
    c.execute('''CREATE TABLE IF NOT EXISTS shorts (  
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        channel_id INTEGER,  
        title TEXT,  
        script TEXT,  
        trigger TEXT,  
        description TEXT,  
        tags TEXT,  
        video_path TEXT,  
        audio_path TEXT,
        subtitles_path TEXT,
        youtube_url TEXT,
        status TEXT DEFAULT 'idea'  
    )''')  
    conn.commit()
    
    # Add migration columns if they don't exist safely
    try:
        c.execute("ALTER TABLE channels ADD COLUMN youtube_credentials TEXT")
        conn.commit()
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE shorts ADD COLUMN audio_path TEXT")
        c.execute("ALTER TABLE shorts ADD COLUMN subtitles_path TEXT")
        c.execute("ALTER TABLE shorts ADD COLUMN youtube_url TEXT")
        conn.commit()
    except Exception:
        pass

    conn.close()

# --- Channel Operations ---
def get_all_channels():
    conn = get_connection()
    c = conn.cursor()
    channels = c.execute("SELECT id, channel_name, niche, subscribers, total_shorts, youtube_credentials FROM channels").fetchall()
    conn.close()
    return channels

def get_channel(channel_id):
    conn = get_connection()
    c = conn.cursor()
    ch = c.execute("SELECT id, channel_name, niche, subscribers, total_shorts, youtube_credentials FROM channels WHERE id=?", (channel_id,)).fetchone()
    conn.close()
    return ch

def add_channel(name, niche, subs, credentials=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO channels (channel_name, niche, subscribers, youtube_credentials) VALUES (?, ?, ?, ?)", (name, niche, subs, credentials))
    conn.commit()
    conn.close()

def update_channel_credentials(channel_id, credentials):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE channels SET youtube_credentials=? WHERE id=?", (credentials, channel_id))
    conn.commit()
    conn.close()

def delete_channel(channel_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE id=?", (channel_id,))
    c.execute("DELETE FROM shorts WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()

# --- Short Operations ---
def add_short(channel_id, title, script, trigger, description, tags, status='idea'):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO shorts   
        (channel_id, title, script, trigger, description, tags, status)   
        VALUES (?, ?, ?, ?, ?, ?, ?)""",  
        (channel_id, title, script, trigger, description, tags, status))  
    short_id = c.lastrowid
    conn.commit()
    conn.close()
    return short_id

def get_all_shorts():
    conn = get_connection()
    c = conn.cursor()
    shorts = c.execute("""
        SELECT s.id, s.channel_id, s.title, s.script, s.trigger, s.description, s.tags, 
               s.video_path, s.audio_path, s.subtitles_path, s.youtube_url, s.status, ch.channel_name, ch.niche 
        FROM shorts s 
        LEFT JOIN channels ch ON s.channel_id = ch.id 
        ORDER BY s.id DESC
    """).fetchall()
    conn.close()
    return shorts

def get_shorts_by_status(status):
    conn = get_connection()
    c = conn.cursor()
    shorts = c.execute("""
        SELECT s.id, s.channel_id, s.title, s.script, s.trigger, s.description, s.tags, 
               s.video_path, s.audio_path, s.subtitles_path, s.youtube_url, s.status, ch.channel_name, ch.niche 
        FROM shorts s 
        LEFT JOIN channels ch ON s.channel_id = ch.id 
        WHERE s.status=?
        ORDER BY s.id DESC
    """, (status,)).fetchall()
    conn.close()
    return shorts

def get_short(short_id):
    conn = get_connection()
    c = conn.cursor()
    s = c.execute("""
        SELECT s.id, s.channel_id, s.title, s.script, s.trigger, s.description, s.tags, 
               s.video_path, s.audio_path, s.subtitles_path, s.youtube_url, s.status, ch.channel_name, ch.niche 
        FROM shorts s 
        LEFT JOIN channels ch ON s.channel_id = ch.id 
        WHERE s.id=?
    """, (short_id,)).fetchone()
    conn.close()
    return s

def update_short_video(short_id, video_path, audio_path, subtitles_path, status='created'):
    conn = get_connection()
    c = conn.cursor()
    
    # Proactively clean up and delete previous rendering files to prevent cluttering disk space!
    prev = c.execute("SELECT video_path, audio_path, subtitles_path FROM shorts WHERE id=?", (short_id,)).fetchone()
    if prev:
        for fpath in prev:
            if fpath and fpath != video_path and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass # Ignore locked system files, they will be freed on exit
                    
    c.execute("""UPDATE shorts SET video_path=?, audio_path=?, subtitles_path=?, status=? WHERE id=?""", 
              (video_path, audio_path, subtitles_path, status, short_id))
    
    s = get_short(short_id)
    if s:
        ch_id = s[1]
        c.execute("UPDATE channels SET total_shorts = total_shorts + 1 WHERE id=?", (ch_id,))
    
    conn.commit()
    conn.close()

def update_short_status(short_id, status, youtube_url=None):
    conn = get_connection()
    c = conn.cursor()
    if youtube_url:
        c.execute("UPDATE shorts SET status=?, youtube_url=? WHERE id=?", (status, youtube_url, short_id))
    else:
        c.execute("UPDATE shorts SET status=? WHERE id=?", (status, short_id))
    conn.commit()
    conn.close()

def delete_short(short_id):
    conn = get_connection()
    c = conn.cursor()
    s = c.execute("SELECT video_path, audio_path, subtitles_path FROM shorts WHERE id=?", (short_id,)).fetchone()
    if s:
        for fpath in s:
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
    c.execute("DELETE FROM shorts WHERE id=?", (short_id,))
    conn.commit()
    conn.close()

# --- Settings & Optimization Operations ---
def get_setting(key, default_val):
    conn = get_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    res = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    if res:
        return res[0]
    return default_val

def set_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
