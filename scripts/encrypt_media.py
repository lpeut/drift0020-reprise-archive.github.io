import os
import json
import base64
import secrets
from Crypto.Cipher import AES

def encrypt_media(data_path='data.json', media_dir='../media'):
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return

    # Load data.json
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get or generate key
    if 'media_encryption_key' not in data:
        print("Generating new encryption key...")
        key = secrets.token_bytes(32) # 256-bit
        data['media_encryption_key'] = base64.b64encode(key).decode('utf-8')
    else:
        print("Using existing encryption key from data.json")
        key = base64.b64decode(data['media_encryption_key'])

    encrypted_count = 0
    # Encrypt files in media directory
    for root, dirs, files in os.walk(media_dir):
        for file in files:
            if file.endswith('.enc'):
                continue
            
            file_path = os.path.join(root, file).replace('\\', '/')
            enc_path = file_path + '.enc'
            
            if os.path.exists(enc_path):
                continue
                
            print(f"Encrypting {file_path}...")
            try:
                with open(file_path, 'rb') as f_in:
                    plaintext = f_in.read()
                
                # AES-GCM encryption
                cipher = AES.new(key, AES.MODE_GCM)
                ciphertext, tag = cipher.encrypt_and_digest(plaintext)
                
                # Store: Nonce (16 bytes) + Tag (16 bytes) + Ciphertext
                with open(enc_path, 'wb') as f_out:
                    f_out.write(cipher.nonce) 
                    f_out.write(tag)
                    f_out.write(ciphertext)
                encrypted_count += 1
            except Exception as e:
                print(f"Failed to encrypt {file_path}: {e}")

    # Update media paths in data.json to point to .enc files
    status_updated_count = 0
    for status in data.get('statuses', []):
        media_paths = status.get('media_paths', [])
        new_paths = []
        updated = False
        for p in media_paths:
            p = p.replace('\\', '/')
            if not p.endswith('.enc'):
                enc_p = p + '.enc'
                if os.path.exists('../' + enc_p):
                    new_paths.append(enc_p)
                    updated = True
                else:
                    new_paths.append(p)
            else:
                new_paths.append(p)
        
        status['media_paths'] = new_paths
        status_updated_count += 1

    # Update users local_avatar_path
    user_updated_count = 0
    for user in data.get('users', []):
        p = user.get('local_avatar_path')
        if p:
            p = p.replace('\\', '/')
            enc_p = p + '.enc'
            if os.path.exists('../' + enc_p):
                user['local_avatar_path'] = enc_p
                user_updated_count += 1
            else:
                user['local_avatar_path'] = p

    # Save data.json with key and updated paths
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Encrypted {encrypted_count} files. Updated {status_updated_count} statuses and {user_updated_count} users in {data_path}.")

if __name__ == "__main__":
    encrypt_media()
