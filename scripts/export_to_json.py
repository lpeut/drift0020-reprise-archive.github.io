import sqlite3
import json
import os

def export_db_to_json(db_path='backup.db', json_path='data.json'):
    # 유저가 언급한 backup.db가 있으면 그것을 우선 사용하도록 수정
    if not os.path.exists(db_path) and os.path.exists('backup.db'):
        db_path = 'backup.db'
        print(f"Using {db_path} as fallback...")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found ({db_path}).")
        return

    # 기존 data.json에서 암호화 키 보존 시도
    existing_key = None
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                existing_key = old_data.get('media_encryption_key')
        except:
            pass

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch users
    cursor.execute("SELECT * FROM users")
    users = []
    for row in cursor.fetchall():
        user = dict(row)
        # .enc 버전이 있으면 경로 업데이트
        p = user.get('local_avatar_path')
        if p:
            p = p.replace('\\', '/')
            if os.path.exists('../' + p + '.enc'):
                user['local_avatar_path'] = p + '.enc'
            else:
                user['local_avatar_path'] = p
        users.append(user)

    # Fetch statuses
    cursor.execute("SELECT * FROM statuses ORDER BY created_at DESC")
    statuses = []
    for row in cursor.fetchall():
        status = dict(row)
        # Parse media_paths JSON string back to list
        media_paths = json.loads(status['media_paths'])
        
        # 만약 해당 파일의 .enc 버전이 존재한다면 .enc 경로로 업데이트
        updated_media_paths = []
        for p in media_paths:
            p = p.replace('\\', '/')
            if os.path.exists('../' + p + '.enc'):
                updated_media_paths.append(p + '.enc')
            else:
                updated_media_paths.append(p)
        status['media_paths'] = updated_media_paths
        
        # Find associated user
        user = next((u for u in users if u['id'] == status['user_id']), None)
        status['user'] = user
        statuses.append(status)

    data = {
        "users": users,
        "statuses": statuses
    }
    
    if existing_key:
        data['media_encryption_key'] = existing_key

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Successfully exported to {json_path}")
    conn.close()

if __name__ == "__main__":
    export_db_to_json()
