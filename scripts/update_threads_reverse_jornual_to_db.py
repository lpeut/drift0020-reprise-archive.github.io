import sqlite3
import json
import os

# --- 설정 ---
DB_NAME = 'backup.db'
JOURNAL_NAME = 'db-journal.json'

def update_db_from_journal():
    # 1. 저널 파일 존재 여부 확인
    if not os.path.exists(JOURNAL_NAME):
        print(f"❌ '{JOURNAL_NAME}' 파일을 찾을 수 없습니다.")
        return

    # 2. 저널 파일 로드
    try:
        with open(JOURNAL_NAME, 'r', encoding='utf-8') as f:
            journal_data = json.load(f)
        print(f"📂 저널 파일을 읽어왔습니다. (데이터: {len(journal_data)}건)")
    except Exception as e:
        print(f"❌ 저널 파일 읽기 중 오류 발생: {e}")
        return

    # 3. DB 연결
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    updated_count = 0
    failed_count = 0
    total = len(journal_data)

    print("🔄 DB 업데이트 작업을 시작합니다...")

    # 4. 데이터 일괄 업데이트
    for status_id, parent_id in journal_data.items():
        try:
            if parent_id == "FAILED":
                # 작업에 실패했던 건은 retry_count만 증가
                cursor.execute("""
                    UPDATE statuses 
                    SET in_reply_to_id = 'FAILED', 
                        retry_count = retry_count + 1 
                    WHERE id = ?
                """, (status_id,))
                failed_count += 1
            else:
                # 성공한 건은 부모 ID를 입력하고 retry_count를 0으로 초기화
                cursor.execute("""
                    UPDATE statuses 
                    SET in_reply_to_id = ?, 
                        retry_count = 0 
                    WHERE id = ?
                """, (parent_id, status_id))
                updated_count += 1

            # 100건마다 진행 상황 출력 및 커밋
            if (updated_count + failed_count) % 100 == 0:
                conn.commit()
                print(f"⏳ 진행 중... [{updated_count + failed_count}/{total}]")

        except Exception as e:
            print(f"⚠️ ID {status_id} 처리 중 오류: {e}")

    # 5. 최종 커밋 및 종료
    conn.commit()
    conn.close()

    print("\n" + "="*30)
    print(f"✨ 작업 완료!")
    print(f"✅ 성공적으로 업데이트: {updated_count}건")
    print(f"⚠️ 실패(FAILED) 기록: {failed_count}건")
    print(f"📊 총 처리: {updated_count + failed_count}건")
    print("="*30)

if __name__ == "__main__":
    update_db_from_journal()