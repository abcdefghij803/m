import json
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, sessions_file: str, api_id: str, api_hash: str):
        """Initialize SessionManager with sessions file path and Telegram API credentials."""
        self.sessions_file = sessions_file
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients = []
        self.load_sessions()

    def load_sessions(self):
        """Load session strings from file and initialize TelegramClient instances."""
        try:
            with open(self.sessions_file, 'r') as f:
                data = json.load(f)
                sessions = data.get('sessions', [])
                for session_string in sessions:
                    # Skip empty or invalid session strings
                    if not session_string or not isinstance(session_string, str):
                        logger.warning(f"Skipping invalid session string: {session_string}")
                        continue
                    client = TelegramClient(session_string, self.api_id, self.api_hash)
                    if self.validate_session(client):
                        self.active_clients.append(client)
                    else:
                        logger.warning(f"Invalid session string: {session_string}")
        except FileNotFoundError:
            logger.warning(f"Sessions file {self.sessions_file} not found, starting with empty sessions.")
            with open(self.sessions_file, 'w') as f:
                json.dump({'sessions': []}, f, indent=4)
        except json.JSONDecodeError:
            logger.error(f"Error decoding sessions file {self.sessions_file}")
            self.active_clients = []

    def validate_session(self, client):
        """Validate a TelegramClient session by attempting to connect."""
        try:
            client.connect()
            if not client.is_user_authorized():
                logger.warning("Session not authorized, skipping.")
                return False
            return True
        except SessionPasswordNeededError:
            logger.error("Two-factor authentication required for session, skipping.")
            return False
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False
        finally:
            if client.is_connected():
                client.disconnect()

    def get_active_sessions(self):
        """Return list of active TelegramClient instances."""
        return self.active_clients

    def save_sessions(self):
        """Save active session strings to file."""
        sessions = [client.session.save() for client in self.active_clients]
        with open(self.sessions_file, 'w') as f:
            json.dump({'sessions': sessions}, f, indent=4)
