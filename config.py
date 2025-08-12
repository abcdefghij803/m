import os
from typing import Dict
from dotenv import load_dotenv

def load_config() -> Dict:
    """Load configuration from environment variables."""
    load_dotenv()
    return {
        'bot_token': os.getenv('BOT_TOKEN', '8056566358:AAFTJ5fmVhVrbSdsASgPpTGDv4tntb_I1vI'),
        'admin_user_id': os.getenv('ADMIN_USER_ID', '7089574265'),
        'sessions_file': 'sessions.json',
        'max_concurrent_tasks': 50,
        'report_interval': 600,  # 10 minutes
        'api_id': os.getenv('API_ID'),
        'api_hash': os.getenv('API_HASH'),
        # UI Configuration
        'support_group': os.getenv('SUPPORT_GROUP', 'https://t.me/GHOULS_SUPPORT'),
        'update_group': os.getenv('UPDATE_GROUP', 'https://t.me/KAISEN_UPDATES'),
        'youtube_channel': os.getenv('YOUTUBE_CHANNEL', 'https://youtube.com/@your_channel'),
        'developer_username': os.getenv('DEVELOPER_USERNAME', 'ixigio')
    }
