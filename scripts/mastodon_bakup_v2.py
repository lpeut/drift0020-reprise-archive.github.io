import os
import sqlite3
import requests
import json
import time
from datetime import datetime
from mastodon import Mastodon, MastodonAPIError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
INSTANCE_URL = os.getenv('INSTANCE_URL')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
DB_NAME = 'backup.db'
MEDIA_DIR = 'media'
AVATAR_DIR = os.path.join(MEDIA_DIR, 'avatars')
START_DATE = datetime(2025, 12, 27)

def check_rate_limit(mastodon):
    """API 리밋 상태를 확인하고 상세 정보를 출력한 뒤 대기합니다."""
    remaining = mastodon.ratelimit_remaining
    limit = mastodon.ratelimit_limit
    status_str = f" [리밋: {remaining}/{limit}]"
    
    if remaining is not None:
        if remaining < 20:
            print(f"\n⚠️ 리밋 임박{status_str}, 30초 휴식...")
            time.sleep(30)
        elif remaining < 50:
            print(f" (속도 조절{status_str})", end=" ")
            time.sleep(2.0)
        else:
            print(f" (리밋 여유{status_str})", end=" ")
            time.sleep(0.5)
    return remaining

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT, display_name TEXT, url TEXT, avatar_url TEXT, local_avatar_path TEXT)''')
    # in_reply_to_id 칼럼 추가
    cursor.execute('''CREATE TABLE IF NOT EXISTS statuses (
        id TEXT PRIMARY KEY, 
        user_id TEXT, 
        content TEXT, 
        spoiler_text TEXT, 
        created_at DATETIME, 
        url TEXT, 
        media_paths TEXT, 
        in_reply_to_id TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.commit()
    return conn

def save_status(conn, status, media_paths):
    # status['in_reply_to_id'] 값을 직접 저장
    parent_id = str(status.get('in_reply_to_id')) if status.get('in_reply_to_id') else "NONE"
    
    conn.cursor().execute('''INSERT OR REPLACE INTO statuses 
        (id, user_id, content, spoiler_text, created_at, url, media_paths, in_reply_to_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
        (str(status['id']), str(status['account']['id']), status['content'], 
         status['spoiler_text'], status['created_at'].isoformat(), status['url'], 
         json.dumps(media_paths), parent_id))
    conn.commit()

# --- (save_user, download_media 함수는 이전과 동일) ---
# ...

def main():
    if not INSTANCE_URL or not ACCESS_TOKEN:
        print("Error: INSTANCE_URL and ACCESS_TOKEN must be set in .env file.")
        return

    mastodon = Mastodon(access_token=ACCESS_TOKEN, api_base_url=INSTANCE_URL)
    conn = init_db()
    
    try:
        me = mastodon.account_verify_credentials()
        # 팔로워 및 타임라인 수집 로직 통합
        target_users = [me]
        
        # ... (팔로워 수집 루프 동일) ...

        for user in target_users:
            print(f"\n>> 처리 중: {user['username']}")
            try:
                statuses = mastodon.account_statuses(user['id'])
                while statuses:
                    for status in statuses:
                        if status['created_at'].replace(tzinfo=None) < START_DATE:
                            statuses = None; break
                        if status['visibility'] != 'direct':
                            # 저장 시 스레드 정보(in_reply_to_id) 자동 포함
                            save_status(conn, status, download_media(status['media_attachments']))
                    
                    if statuses:
                        check_rate_limit(mastodon)
                        statuses = mastodon.fetch_next(statuses)
            except MastodonAPIError as e:
                if "429" in str(e):
                    time.sleep(60)
                else: print(f"Error: {e}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()