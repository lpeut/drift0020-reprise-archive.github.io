import os
import sqlite3
import requests
import json
from datetime import datetime
from mastodon import Mastodon, MastodonNotFoundError, MastodonNetworkError, MastodonAPIError
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
# Note: Ensure your ACCESS_TOKEN has 'read' or 'read:accounts' and 'read:statuses' scopes.
INSTANCE_URL = os.getenv('INSTANCE_URL')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
DB_NAME = 'backup.db'
MEDIA_DIR = 'media'
AVATAR_DIR = os.path.join(MEDIA_DIR, 'avatars')
START_DATE = datetime(2025, 12, 27)  # Fetch statuses from this date onwards

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT,
        display_name TEXT,
        url TEXT,
        avatar_url TEXT,
        local_avatar_path TEXT
    )
    ''')
    
    # Statuses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statuses (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        content TEXT,
        spoiler_text TEXT, -- CW (Content Warning) field
        created_at DATETIME,
        url TEXT,
        media_paths TEXT, -- Local paths stored as JSON string
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    
    conn.commit()
    return conn

def download_avatar(user_id, avatar_url):
    if not os.path.exists(AVATAR_DIR):
        os.makedirs(AVATAR_DIR)
    
    if not avatar_url:
        return None

    file_extension = avatar_url.split('.')[-1].split('?')[0]
    if len(file_extension) > 4: file_extension = 'png'
    
    filename = f"{user_id}.{file_extension}"
    local_path = os.path.join(AVATAR_DIR, filename)
    
    if os.path.exists(local_path):
        return local_path

    try:
        response = requests.get(avatar_url, timeout=10)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return local_path
    except Exception as e:
        print(f"  Error downloading avatar for {user_id}: {e}")
    
    return None

def save_user(conn, user):
    avatar_url = user.get('avatar')
    local_avatar_path = download_avatar(user['id'], avatar_url)

    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO users (id, username, display_name, url, avatar_url, local_avatar_path)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(user['id']), user['username'], user['display_name'], user['url'], avatar_url, local_avatar_path))
    conn.commit()

def save_status(conn, status, media_paths):
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO statuses (id, user_id, content, spoiler_text, created_at, url, media_paths)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(status['id']),
        str(status['account']['id']),
        status['content'],
        status['spoiler_text'],
        status['created_at'].isoformat(),
        status['url'],
        json.dumps(media_paths)
    ))
    conn.commit()

# --- Media Downloader ---
def download_media(media_attachments):
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)
    
    local_paths = []
    for attachment in media_attachments:
        url = attachment['url']
        file_extension = url.split('.')[-1].split('?')[0]
        filename = f"{attachment['id']}.{file_extension}"
        local_path = os.path.join(MEDIA_DIR, filename)
        
        if os.path.exists(local_path):
            local_paths.append(local_path)
            continue

        try:
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                local_paths.append(local_path)
                print(f"  Downloaded: {filename}")
            else:
                print(f"  Failed to download media: {url} (Status: {response.status_code})")
        except Exception as e:
            print(f"  Error downloading media {url}: {e}")
            
    return local_paths

# --- Main Logic ---
def main():
    if not INSTANCE_URL or not ACCESS_TOKEN:
        print("Error: INSTANCE_URL and ACCESS_TOKEN must be set in .env file.")
        return

    # Initialize Mastodon API
    mastodon = Mastodon(
        access_token=ACCESS_TOKEN,
        api_base_url=INSTANCE_URL,
        ratelimit_method='wait' # Automatically wait for rate limits
    )

    conn = init_db()
    
    try:
        # 1. Get current user
        me = mastodon.account_verify_credentials()
        save_user(conn, me)
        target_users = [me]
        print(f"Authenticated as: {me['username']}")

        # 2. Get followers
        print("Fetching followers...")
        followers = mastodon.account_followers(me['id'])
        while followers:
            for follower in followers:
                save_user(conn, follower)
                target_users.append(follower)
            followers = mastodon.fetch_next(followers)
            time.sleep(1) # Small delay
        
        print(f"Total users to process (self + followers): {len(target_users)}")

        # 3. Fetch statuses for each user
        for user in target_users:
            print(f"Processing user: {user['username']} ({user['id']})")
            
            # Fetch statuses with pagination
            statuses = mastodon.account_statuses(user['id'])
            
            while statuses:
                reached_start_date = False
                for status in statuses:
                    # Check date filter
                    if status['created_at'].replace(tzinfo=None) < START_DATE:
                        reached_start_date = True
                        break
                    
                    # IGNORE DM (visibility: direct)
                    if status['visibility'] == 'direct':
                        # print(f"  Skipping DM: ID {status['id']}")
                        continue
                    
                    # Download media
                    media_paths = download_media(status['media_attachments'])
                    
                    # Save to DB
                    save_status(conn, status, media_paths)
                
                if reached_start_date:
                    print(f"  Reached start date for {user['username']}.")
                    break
                
                # Fetch next page
                statuses = mastodon.fetch_next(statuses)
                if statuses:
                    print(f"  Fetching next page of statuses for {user['username']}...")
                    time.sleep(1.1)

        print("Backup completed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
