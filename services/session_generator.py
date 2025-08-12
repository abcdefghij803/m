import asyncio
from telethon import TelegramClient
from pyrogram import Client
import logging

logger = logging.getLogger(__name__)

class SessionGenerator:
    """Handle session string generation for different client types."""
    
    @staticmethod
    async def generate_telethon_session(api_id: str, api_hash: str, phone: str = None, bot_token: str = None) -> str:
        """Generate Telethon session string."""
        try:
            if bot_token:
                # Bot session
                client = TelegramClient('temp_session', api_id, api_hash)
                await client.start(bot_token=bot_token)
            else:
                # User session
                client = TelegramClient('temp_session', api_id, api_hash)
                await client.start(phone=phone)
            
            session_string = client.session.save()
            await client.disconnect()
            return session_string
            
        except Exception as e:
            logger.error(f"Error generating Telethon session: {e}")
            raise e
    
    @staticmethod
    async def generate_pyrogram_session(api_id: str, api_hash: str, phone: str = None, bot_token: str = None) -> str:
        """Generate Pyrogram session string."""
        try:
            if bot_token:
                # Bot session
                app = Client("temp_session", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
            else:
                # User session
                app = Client("temp_session", api_id=api_id, api_hash=api_hash, phone_number=phone)
            
            await app.start()
            session_string = await app.export_session_string()
            await app.stop()
            return session_string
            
        except Exception as e:
            logger.error(f"Error generating Pyrogram session: {e}")
            raise e
    
    @staticmethod
    def validate_credentials(api_id: str, api_hash: str) -> bool:
        """Validate API credentials format."""
        try:
            int(api_id)
            return len(api_hash) == 32 and api_hash.isalnum()
        except ValueError:
            return False
