import sqlite3
import time
import json
import os
from mastodon import Mastodon, MastodonAPIError, MastodonRatelimitError
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
INSTANCE_URL = os.getenv('INSTANCE_URL')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
DB_NAME = 'backup.db'
JOURNAL_NAME = 'db-journal.json' 

def journal_process():
    if not INSTANCE_URL or not ACCESS_TOKEN:
        print("Error: INSTANCE_URL and ACCESS_TOKEN must be set in .env file.")
        return

    mastodon = Mastodon(access_token=ACCESS_TOKEN, api_base_url=INSTANCE_URL)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. 기존 저널 파일 로드
    journal_data = {}
    if os.path.exists(JOURNAL_NAME):
        try:
            with open(JOURNAL_NAME, 'r', encoding='utf-8') as f:
                journal_data = json.load(f)
            print(f"📂 저널 파일을 불러왔습니다. (이미 처리된 데이터: {len(journal_data)}건)")
        except Exception as e:
            print(f"⚠️ 저널 파일 읽기 오류: {e}")

    # 2. 실제로 확인이 필요한(NULL) ID 목록 가져오기 (ID 역순)
    # NONE으로 이미 판명된 툿은 리밋 보호를 위해 쿼리에서 제외합니다.
    query = """
        SELECT id FROM statuses 
        WHERE in_reply_to_id IS NULL OR in_reply_to_id = 'FAILED'
        ORDER BY id DESC
    """
    cursor.execute(query)
    all_db_ids = [row[0] for row in cursor.fetchall()]
    
    # 이미 저널에 성공 기록이 있는 ID는 제외
    target_ids = [sid for sid in all_db_ids if journal_data.get(str(sid)) not in ["NONE", "SUCCESS"]]
    
    total = len(target_ids)
    if total == 0:
        print("🎉 모든 툿의 부모 정보를 확인했습니다.")
        conn.close()
        return

    print(f"🔄 확인이 필요한 툿: {total}건. 작업을 시작합니다.")

    try:
        for i, status_id in enumerate(target_ids):
            remaining = mastodon.ratelimit_remaining
            limit = mastodon.ratelimit_limit
            
            try:
                # 3. API 호출
                status_info = mastodon.status(status_id)
                parent_id = str(status_info['in_reply_to_id']) if status_info.get('in_reply_to_id') else "NONE"
                
                # 4. 저널 데이터 업데이트
                journal_data[str(status_id)] = parent_id
                
                # 5. 주기적으로 파일 저장 (20개마다)
                if (i + 1) % 20 == 0:
                    with open(JOURNAL_NAME, 'w', encoding='utf-8') as f:
                        json.dump(journal_data, f, ensure_ascii=False, indent=2)
                    print(f"💾 진행 상황 저장됨 (현재: {i+1}/{total})")

                print(f"✅ [{i + 1}/{total}] ID:{status_id} | 부모: {parent_id} | 리밋: {remaining}/{limit}")
                
                # 속도 조절
                time.sleep(1.0 if remaining < 10 else 0.3)
                
            except MastodonRatelimitError as e:
                wait_time = max(e.rate_limit_reset - time.time(), 30)
                print(f"\n❌ 리밋 초과! {wait_time:.0f}초 대기...")
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"\n❌ 오류 발생(ID: {status_id}): {e}")
                journal_data[str(status_id)] = "FAILED"
                continue

    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
    
    finally:
        # 6. 최종 저장 및 종료
        with open(JOURNAL_NAME, 'w', encoding='utf-8') as f:
            json.dump(journal_data, f, ensure_ascii=False, indent=2)
        conn.close()
        print(f"✨ 작업 완료! 저널 파일({JOURNAL_NAME})이 업데이트되었습니다.")

if __name__ == "__main__":
    journal_process()