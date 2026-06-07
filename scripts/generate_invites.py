import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import random
import string
import os

def generate_invite_codes(count=40):
    """
    Generates unique invite codes and uploads them to Firebase Firestore.
    Requires a service account key file (serviceAccountKey.json).
    """
    
    # 1. Firebase 인증 (서비스 계정 키 필요)
    key_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
    
    if not os.path.exists(key_path):
        print("Error: 'serviceAccountKey.json' file not found in scripts folder.")
        print("Please download it from Firebase Console -> Project Settings -> Service Accounts.")
        return

    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print(f"Generating {count} invite codes...")
    
    codes = []
    for _ in range(count):
        # 8자리 랜덤 대문자+숫자 조합 (예: ABCD-1234 형식)
        part1 = ''.join(random.choices(string.ascii_uppercase, k=4))
        part2 = ''.join(random.choices(string.digits, k=4))
        code = f"{part1}-{part2}"
        codes.append(code)

    # 2. Firestore 업로드
    batch = db.batch()
    for code in codes:
        doc_ref = db.collection('invites').document(code)
        batch.set(doc_ref, {
            'used': False,
            'createdAt': firestore.SERVER_TIMESTAMP
        })

    batch.commit()
    
    # 3. 결과 출력 및 파일 저장 (나중에 지인들에게 보내기 위함)
    output_path = os.path.join(os.path.dirname(__file__), 'invite_codes.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        for code in codes:
            f.write(f"{code}\n")

    print(f"Successfully generated and uploaded {count} codes.")
    print(f"Codes saved to: {output_path}")
    print("WARNING: Keep these codes secure and share them one by one.")

if __name__ == "__main__":
    generate_invite_codes(40)
