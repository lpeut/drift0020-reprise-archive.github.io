import sqlite3
import time
import os
from mastodon import Mastodon, MastodonAPIError, MastodonRatelimitError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- 설정 ---
INSTANCE_URL = os.getenv('INSTANCE_URL')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
DB_NAME = 'backup.db'

def batch_process():
    if not INSTANCE_URL or not ACCESS_TOKEN:
        print("Error: INSTANCE_URL and ACCESS_TOKEN must be set in .env file.")
        return

    mastodon = Mastodon(access_token=ACCESS_TOKEN, api_base_url=INSTANCE_URL)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM statuses 
        WHERE (in_reply_to_id IS NULL OR in_reply_to_id = 'FAILED') 
        AND retry_count < 3 
        ORDER BY id DESC
    """)
    all_ids = [row[0] for row in cursor.fetchall()]
    
    total = len(all_ids)
    print(f"🔄 처리 대상: {total}건. 작업을 시작합니다.")

    for i, status_id in enumerate(all_ids):
        # 현재 리밋 정보 갱신
        remaining = mastodon.ratelimit_remaining
        limit = mastodon.ratelimit_limit
        
        try:
            # 1. API 호출
            status_info = mastodon.status(status_id)
            parent_id = str(status_info['in_reply_to_id']) if status_info.get('in_reply_to_id') else "NONE"
            
            # 2. DB 업데이트
            cursor.execute("UPDATE statuses SET in_reply_to_id = ?, retry_count = 0 WHERE id = ?", (parent_id, status_id))
            
            # 3. 배치 커밋 (40개마다 수행)
            if (i + 1) % 40 == 0:
                conn.commit()
            
            # 4. 진행 상황 및 리밋 정보 출력
            print(f"✅ [{i + 1}/{total}] ID:{status_id} | 리밋: {remaining}/{limit} | 부모: {parent_id}")
            
            # 5. 속도 조절
            if remaining < 10:
                time.sleep(1.0)
            else:
                time.sleep(0.3)
            
        except MastodonRatelimitError as e:
            reset_time = e.rate_limit_reset
            wait_time = max(reset_time - time.time(), 30)
            print(f"\n❌ 리밋 초과! 초기화까지 {wait_time:.0f}초 대기 중... (현재 리밋: {remaining})")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"\n❌ 오류 발생(ID: {status_id}): {e}")
            cursor.execute("UPDATE statuses SET in_reply_to_id = 'FAILED', retry_count = retry_count + 1 WHERE id = ?", (status_id,))
            conn.commit()

    conn.commit()
    conn.close()
    print("✨ 모든 작업 완료!")

if __name__ == "__main__":
    batch_process()