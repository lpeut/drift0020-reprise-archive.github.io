import os
import sqlite3
import time
from mastodon import Mastodon
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

INSTANCE_URL = os.getenv('INSTANCE_URL')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
DB_NAME = 'backup.db'

def main():
    if not INSTANCE_URL or not ACCESS_TOKEN:
        print("Error: INSTANCE_URL and ACCESS_TOKEN must be set in .env file.")
        return

    if not os.path.exists(DB_NAME):
        print(f"❌ 에러: {DB_NAME} 파일이 존재하지 않습니다.")
        return

    mastodon = Mastodon(access_token=ACCESS_TOKEN, api_base_url=INSTANCE_URL)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # [단계 1] 스키마 준비
    try:
        cursor.execute("ALTER TABLE statuses ADD COLUMN in_reply_to_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE statuses ADD COLUMN retry_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()

    # [단계 2] 조회 대상 선정 (재시도 횟수가 3 미만인 글들)
    cursor.execute("SELECT id FROM statuses WHERE (in_reply_to_id IS NULL OR in_reply_to_id = 'FAILED') AND retry_count < 3")
    status_ids = [row[0] for row in cursor.fetchall()]
    
    total_count = len(status_ids)
    print(f"🔄 처리 대상: {total_count}건")

    if total_count == 0:
        print("🎉 업데이트할 데이터가 없습니다.")
        conn.close()
        return

    # [단계 3] 적응형 루프
    for i, status_id in enumerate(status_ids, 1):
        try:
            # 1. API 리밋 체크 (mastodon.ratelimit_remaining 활용)
            # 요청 전 남은 리밋 확인
            remaining = mastodon.ratelimit_remaining
            
            # 2. 적응형 슬립 로직
            if remaining < 20: # 리밋이 20 미만으로 떨어지면 30초 대기
                print(f"\n⚠️ 리밋 임박({remaining}), 30초간 대기합니다...")
                time.sleep(30)
            else:
                time.sleep(0.5) # 여유 있을 땐 0.5초 간격으로 처리

            print(f"[{i}/{total_count}] ID:{status_id} 조회 중... (남은 리밋: {remaining})", end=" ")
            
            status_info = mastodon.status(status_id)
            parent_id = str(status_info['in_reply_to_id']) if status_info['in_reply_to_id'] else "NONE"
            
            cursor.execute("UPDATE statuses SET in_reply_to_id = ?, retry_count = 0 WHERE id = ?", (parent_id, status_id))
            conn.commit()
            print(f"✅ 완료: {parent_id}")

        except Exception as e:
            # 리밋 초과 에러(429) 감지 시 특별 처리
            if "429" in str(e):
                print("\n❌ 429 에러 발생! 60초 대기 후 재시도.")
                time.sleep(60)
            else:
                print(f"❌ 실패: {e}")
                cursor.execute("UPDATE statuses SET in_reply_to_id = 'FAILED', retry_count = retry_count + 1 WHERE id = ?", (status_id,))
                conn.commit()

    print(f"\n✨ 작업 종료.")
    conn.close()

if __name__ == "__main__":
    main()