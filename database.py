import sqlite3

DB_FILE = "subscriptions.db"

def init_db():
    """데이터베이스와 테이블을 초기화합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            youtube_channel_id TEXT NOT NULL,
            UNIQUE(channel_id, youtube_channel_id)
        )
    ''')
    conn.commit()
    conn.close()

def add_subscription(server_id, channel_id, youtube_channel_id):
    """새로운 구독 정보를 추가합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subscriptions (server_id, channel_id, youtube_channel_id) VALUES (?, ?, ?)",
                       (str(server_id), str(channel_id), youtube_channel_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError: # 이미 존재하는 구독일 경우
        return False
    finally:
        conn.close()

def remove_subscription(channel_id, youtube_channel_id):
    """기존 구독 정보를 삭제합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE channel_id = ? AND youtube_channel_id = ?",
                   (str(channel_id), youtube_channel_id))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

def get_all_youtube_channels():
    """데이터베이스에 등록된 모든 유니크한 유튜브 채널 ID 목록을 반환합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT youtube_channel_id FROM subscriptions")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    return channels

def get_subscribers(youtube_channel_id):
    """특정 유튜브 채널을 구독하는 모든 디스코드 채널 ID 목록을 반환합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM subscriptions WHERE youtube_channel_id = ?", (youtube_channel_id,))
    subscribers = [int(row[0]) for row in cursor.fetchall()]
    conn.close()
    return subscribers