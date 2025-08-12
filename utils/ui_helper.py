from typing import List, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class UIHelper:
    """Helper class for creating consistent UI elements."""
    
    @staticmethod
    def create_main_menu() -> InlineKeyboardMarkup:
        """Create the main menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("📤 START REPORTING", callback_data="start_report"),
                InlineKeyboardButton("📊 VIEW STATUS", callback_data="view_status")
            ],
            [
                InlineKeyboardButton("🔥 GENERATE STRING SESSION 🔥", callback_data="generate_session")
            ],
            [
                InlineKeyboardButton("⚙️ MANAGE SESSIONS", callback_data="manage_sessions"),
                InlineKeyboardButton("👑 PREMIUM PANEL", callback_data="premium_panel")
            ],
            [
                InlineKeyboardButton("💬 SUPPORT GROUP", url="https://t.me/grandxmasti"),
                InlineKeyboardButton("🔄 UPDATE GROUP", url="https://t.me/blasterUPDATES")
            ],
            [
                InlineKeyboardButton("📺 MY CHANNEL", url="https://t.me/btw_moon")
            ],
            [
                InlineKeyboardButton("🔥 DEVELOPER 🔥", callback_data="developer_info")
            ],
            [
                InlineKeyboardButton("ℹ️ ABOUT", callback_data="about_info"),
                InlineKeyboardButton("❓ HELP", callback_data="help_info")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_session_type_menu() -> InlineKeyboardMarkup:
        """Create session type selection menu."""
        keyboard = [
            [
                InlineKeyboardButton("TELETHON", callback_data="session_type_telethon"),
                InlineKeyboardButton("PYROGRAM", callback_data="session_type_pyrogram")
            ],
            [
                InlineKeyboardButton("TELETHON BOT", callback_data="session_type_telethon_bot"),
                InlineKeyboardButton("PYROGRAM BOT", callback_data="session_type_pyrogram_bot")
            ],
            [InlineKeyboardButton("🔙 BACK", callback_data="back_to_main")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="close")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def format_status_message(session_count: int, task_count: int, premium_count: int, logs: List[str]) -> str:
        """Format the status message with proper styling."""
        log_text = "\\n".join([line.strip().replace(".", "\\.") for line in logs[-5:]])
        
        return (
            "📊 **BOT STATUS DASHBOARD**\n\n"
            "🔢 **STATISTICS:**\n"
            f"├ 📱 Active Sessions: `{session_count}`\n"
            f"├ 🚀 Running Tasks: `{task_count}`\n"
            f"├ 👑 Premium Users: `{premium_count}`\n"
            f"└ 💾 System Status: `Online`\n\n"
            "📋 **RECENT ACTIVITY:**\n"
            f"```\n{log_text}\n```\n\n"
            f"⏰ **Last Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
    
    @staticmethod
    def format_welcome_message(username: str, is_admin: bool, stats: Dict) -> str:
        """Format the welcome message with user-specific content."""
        user_type = "OWNER" if is_admin else "PREMIUM"
        
        return (
            f"✨ **Hi {username} {user_type}** ✨\n\n"
            "🤖 **I CAN GENERATE PYROGRAM AND TELETHON STRING SESSION\\.**\n\n"
            "📊 **CURRENT STATUS:**\n"
            f"├ 📱 Active Sessions: `{stats.get('sessions', 0)}`\n"
            f"├ 🚀 Running Tasks: `{stats.get('tasks', 0)}`\n"
            f"├ 👑 Premium Users: `{stats.get('premium', 0)}`\n"
            f"└ ⏰ Server Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
            "🎯 **USE BELOW BUTTONS TO START OPERATIONS\\.**\n\n"
            "🔥 **MAINTAINED BY:** `ᴋ ᴀ ɪ ꜱ ᴇ ɴ` 🔥"
        )
