import os
import json
import base64
import hashlib
import zlib
from Crypto.Cipher import AES

def encrypt_file(filepath, key):
    with open(filepath, 'rb') as f:
        plaintext = f.read()

    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    
    encrypted_data = cipher.nonce + tag + ciphertext
    
    with open(filepath + '.enc', 'wb') as f_out:
        f_out.write(encrypted_data)
    
    print(f"Encrypted: {filepath} -> {filepath}.enc")

def encrypt_data(base_dir, key):
    input_path = os.path.join(base_dir, 'data.json')
    if not os.path.exists(input_path):
        print("Error: data.json not found.")
        return

    with open(input_path, 'rb') as f:
        plaintext = f.read()

    # 데이터 압축
    compressed_data = zlib.compress(plaintext)

    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(compressed_data)
    
    print(f"Nonce size: {len(cipher.nonce)}")
    print(f"Tag size: {len(tag)}")
    print(f"Ciphertext size: {len(ciphertext)}")
    
    full_data = cipher.nonce + tag + ciphertext
    
    split_idx = len(full_data) // 2
    
    with open(os.path.join(base_dir, 'data_part1.enc'), 'wb') as f_out:
        f_out.write(full_data[:split_idx])
    with open(os.path.join(base_dir, 'data_part2.enc'), 'wb') as f_out:
        f_out.write(full_data[split_idx:])
    print("Data compressed, encrypted, and split into data_part1.enc and data_part2.enc")

def encrypt_media(base_dir, key):
    media_dir = os.path.join(base_dir, '..', 'media')
    if not os.path.exists(media_dir):
        print("Error: media directory not found.")
        return
    
    for root, dirs, files in os.walk(media_dir):
        for filename in files:
            if not filename.endswith('.enc'):
                filepath = os.path.join(root, filename)
                encrypt_file(filepath, key)
    print("Media files encrypted.")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    password = input("Enter master password: ").strip()
    key = hashlib.sha256(password.encode()).digest()

    choice = input("Select: (1) Data, (2) Media, (3) Both: ").strip()
    
    if choice in ['1', '3']:
        encrypt_data(base_dir, key)
    if choice in ['2', '3']:
        encrypt_media(base_dir, key)

if __name__ == "__main__":
    main()
