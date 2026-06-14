import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
UPLOAD_DIR = os.path.join(BASE_DIR, 'data', 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'data', 'uploads.db')


def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn):
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(uploads)')
    columns = [row['name'] for row in cur.fetchall()]
    if 'analysis_json' not in columns:
        cur.execute('ALTER TABLE uploads ADD COLUMN analysis_json TEXT')
        conn.commit()


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            title TEXT,
            authors TEXT,
            pub_date TEXT,
            uploaded_at TEXT NOT NULL,
            analysis_json TEXT
        )
        '''
    )
    conn.commit()
    _ensure_schema(conn)
    conn.close()


def save_file(file_bytes: bytes, filename: str, title: Optional[str] = None, authors: Optional[str] = None, pub_date: Optional[str] = None, analysis_json: Optional[str] = None) -> Dict:
    ensure_dirs()
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    safe_name = f"{timestamp}__{os.path.basename(filename)}"
    stored_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(stored_path, 'wb') as fh:
        fh.write(file_bytes)

    uploaded_at = datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO uploads (filename, stored_path, title, authors, pub_date, uploaded_at, analysis_json) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (filename, stored_path, title, authors, pub_date, uploaded_at, analysis_json)
    )
    uid = cur.lastrowid
    conn.commit()
    conn.close()
    # Write a simple metadata JSON next to the stored file as a robust fallback
    try:
        meta = {
            'id': uid,
            'filename': filename,
            'stored_path': stored_path,
            'title': title,
            'authors': authors,
            'pub_date': pub_date,
            'uploaded_at': uploaded_at,
            'analysis_json': analysis_json,
        }
        meta_path = stored_path + '.meta.json'
        with open(meta_path, 'w', encoding='utf-8') as mf:
            json.dump(meta, mf)
    except Exception:
        # Don't fail upload if metadata file cannot be written
        pass
    return {
        'id': uid,
        'filename': filename,
        'stored_path': stored_path,
        'title': title,
        'authors': authors,
        'pub_date': pub_date,
        'uploaded_at': uploaded_at,
        'analysis_json': analysis_json,
    }


def save_analysis(uid: int, analysis_json: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE uploads SET analysis_json = ? WHERE id = ?', (analysis_json, uid))
    conn.commit()
    conn.close()


def list_files(limit: int = 100) -> List[Dict]:
    ensure_dirs()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, filename, stored_path, title, authors, pub_date, uploaded_at, analysis_json FROM uploads ORDER BY uploaded_at DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    results = [dict(r) for r in rows]

    # Fallback: if DB has no rows, read metadata files from disk
    if not results:
        try:
            for fname in os.listdir(UPLOAD_DIR):
                if fname.endswith('.meta.json'):
                    meta_path = os.path.join(UPLOAD_DIR, fname)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as mf:
                            data = json.load(mf)
                            results.append(data)
                    except Exception:
                        continue
        except Exception:
            pass

    return results


def get_file_record(uid: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, filename, stored_path, title, authors, pub_date, uploaded_at, analysis_json FROM uploads WHERE id = ?', (uid,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)

    # Fallback: try to find a meta.json with matching id
    try:
        for fname in os.listdir(UPLOAD_DIR):
            if fname.endswith('.meta.json'):
                meta_path = os.path.join(UPLOAD_DIR, fname)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as mf:
                        data = json.load(mf)
                        if int(data.get('id', -1)) == int(uid):
                            return data
                except Exception:
                    continue
    except Exception:
        pass

    return None


def update_file_metadata(uid: int, title: Optional[str] = None, authors: Optional[str] = None, pub_date: Optional[str] = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    updates = []
    params = []
    if title is not None:
        updates.append('title = ?')
        params.append(title)
    if authors is not None:
        updates.append('authors = ?')
        params.append(authors)
    if pub_date is not None:
        updates.append('pub_date = ?')
        params.append(pub_date)

    if updates:
        params.append(uid)
        cur.execute(f'UPDATE uploads SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
    conn.close()


init_db()
