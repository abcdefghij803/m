import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from telethon import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.users import GetUsersRequest
from telethon.errors import SessionPasswordNeededError, FloodWaitError, UserAlreadyParticipantError
from telethon.tl.types import InputReportReasonSpam, InputReportReasonViolence, InputReportReasonPornography
import re
import uuid
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, FloodWait

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_LINK, WAITING_FOR_API_ID, WAITING_FOR_API_HASH, WAITING_FOR_PHONE, WAITING_FOR_OTP = range(5)

class MassReporterBot:
    def __init__(self):
        # Load config from environment variables with defaults
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_user_id = os.getenv('ADMIN_USER_ID')
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        
        # Use the specified image URL
        self.welcome_image = os.getenv('WELCOME_IMAGE_URL', 'https://i.ibb.co/HfpFXq02/x.jpg')
        self.status_image = os.getenv('STATUS_IMAGE_URL', 'https://i.ibb.co/HfpFXq02/x.jpg')
        self.session_image = os.getenv('SESSION_IMAGE_URL', 'https://i.ibb.co/HfpFXq02/x.jpg')
        self.report_image = os.getenv('REPORT_IMAGE_URL', 'https://i.ibb.co/HfpFXq02/x.jpg')
        self.premium_image = os.getenv('PREMIUM_IMAGE_URL', 'https://i.ibb.co/HfpFXq02/x.jpg')
        
        # Reporting settings
        self.report_interval = int(os.getenv('REPORT_INTERVAL', '5'))
        self.max_reports_per_session = int(os.getenv('MAX_REPORTS_PER_SESSION', '10'))
        self.session_cooldown = int(os.getenv('SESSION_COOLDOWN', '300'))
        
        # Updated social links and developer info
        self.vouch_channel = os.getenv('VOUCH_CHANNEL', 'https://t.me/blasterrproofs')
        self.update_channel = os.getenv('UPDATE_CHANNEL', 'https://t.me/blasterupdates')
        self.telegram_channel = os.getenv('TELEGRAM_CHANNEL', 'https://t.me/btw_moon')
        self.developer_username = os.getenv('DEVELOPER_USERNAME', 'rizz_xfx')
        self.developer_name = os.getenv('DEVELOPER_NAME', 'ᴏᴡɴᴇʀ')
        
        if not all([self.bot_token, self.admin_user_id]):
            raise ValueError("BOT_TOKEN and ADMIN_USER_ID are required!")
        
        self.sessions = []
        self.premium_users = {}
        self.active_tasks = {}
        self.session_usage = {}
        self.app = None
        self.temp_clients = {}  # For session generation
        
        # Load data
        self.load_sessions()
        self.load_premium_users()

    def load_sessions(self):
        """Load session strings from file."""
        try:
            if os.path.exists('sessions.json'):
                with open('sessions.json', 'r') as f:
                    data = json.load(f)
                    self.sessions = data.get('sessions', [])
                    logger.info(f"Loaded {len(self.sessions)} sessions")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = []

    def save_sessions(self):
        """Save sessions to file."""
        try:
            with open('sessions.json', 'w') as f:
                json.dump({'sessions': self.sessions}, f, indent=2)
            logger.info(f"Saved {len(self.sessions)} sessions")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

    def load_premium_users(self):
        """Load premium users."""
        try:
            if os.path.exists('premium_users.json'):
                with open('premium_users.json', 'r') as f:
                    data = json.load(f)
                    self.premium_users = data.get('premium_users', {})
                    logger.info(f"Loaded {len(self.premium_users)} premium users")
        except Exception as e:
            logger.error(f"Error loading premium users: {e}")
            self.premium_users = {}

    def save_premium_users(self):
        """Save premium users."""
        try:
            with open('premium_users.json', 'w') as f:
                json.dump({'premium_users': self.premium_users}, f, indent=2)
            logger.info(f"Saved {len(self.premium_users)} premium users")
        except Exception as e:
            logger.error(f"Error saving premium users: {e}")

    def escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def is_authorized(self, update: Update) -> bool:
        """Check if user is authorized."""
        user_id = str(update.effective_user.id)
        
        # Check if admin
        if user_id == self.admin_user_id:
            return True
            
        # Check if premium user with valid access
        if user_id in self.premium_users:
            try:
                expiry = datetime.strptime(self.premium_users[user_id], "%Y-%m-%d %H:%M:%S")
                if datetime.now() < expiry:
                    return True
                else:
                    # Remove expired user
                    del self.premium_users[user_id]
                    self.save_premium_users()
                    logger.info(f"Removed expired premium user: {user_id}")
            except Exception as e:
                logger.error(f"Error checking premium user {user_id}: {e}")
                
        return False

    def is_admin_query(self, query) -> bool:
        """Check if callback query is from admin."""
        return str(query.from_user.id) == self.admin_user_id

    def is_admin(self, update: Update) -> bool:
        """Check if user is admin."""
        return str(update.effective_user.id) == self.admin_user_id

    def get_available_sessions(self) -> List[str]:
        """Get sessions that are not in cooldown."""
        current_time = datetime.now()
        available = []
        
        for session in self.sessions:
            if session not in self.session_usage:
                available.append(session)
            else:
                last_used = self.session_usage[session].get('last_used')
                flood_wait_until = self.session_usage[session].get('flood_wait_until')
                
                # Check flood wait
                if flood_wait_until:
                    try:
                        flood_time = datetime.strptime(flood_wait_until, "%Y-%m-%d %H:%M:%S")
                        if current_time < flood_time:
                            continue
                    except:
                        pass
                
                # Check regular cooldown
                if last_used:
                    try:
                        last_used_time = datetime.strptime(last_used, "%Y-%m-%d %H:%M:%S")
                        if (current_time - last_used_time).seconds >= self.session_cooldown:
                            available.append(session)
                    except:
                        available.append(session)
                else:
                    available.append(session)
        
        return available

    async def safe_send_photo(self, chat_id, photo_url, caption, reply_markup=None, parse_mode=None):
        """Safely send photo with fallback to text."""
        try:
            await self.app.bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return True
            except Exception as e2:
                logger.error(f"Error sending fallback message: {e2}")
                return False

    async def safe_edit_message(self, query, text, reply_markup=None, parse_mode=None):
        """Safely edit message with error handling."""
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            try:
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return True
            except Exception as e2:
                logger.error(f"Error sending new message: {e2}")
                return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler with image."""
        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"
        
        if not self.is_authorized(update):
            unauthorized_msg = (
                "🚫 *ACCESS DENIED*\n\n"
                "❌ Unauthorized access\\. Admin or premium users only\\.\n\n"
                "💎 To get premium access, contact the admin\\.\n"
                "👨‍💻 Developer: @" + self.escape_markdown(self.developer_username)
            )
            await self.safe_send_photo(
                chat_id=update.effective_chat.id,
                photo_url=self.welcome_image,
                caption=unauthorized_msg,
                parse_mode='MarkdownV2'
            )
            return

        # Get stats
        session_count = len(self.sessions)
        available_sessions = len(self.get_available_sessions())
        task_count = len(self.active_tasks)
        premium_count = len([u for u, exp in self.premium_users.items() 
                           if datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > datetime.now()])

        user_type = 'OWNER' if self.is_admin(update) else 'PREMIUM'
        escaped_username = self.escape_markdown(username)
        escaped_dev_name = self.escape_markdown(self.developer_name)
        current_time = datetime.now().strftime('%H:%M:%S')
        
        welcome_msg = (
            "✨ *Hi " + escaped_username + " " + user_type + "* ✨\n\n"
            "🤖 *ADVANCED TELEGRAM MASS REPORTER & SESSION GENERATOR*\n\n"
            "📊 *CURRENT STATUS:*\n"
            "├ 📱 Total Sessions: `" + str(session_count) + "`\n"
            "├ 🟢 Available Sessions: `" + str(available_sessions) + "`\n"
            "├ 🚀 Running Tasks: `" + str(task_count) + "`\n"
            "├ 👑 Premium Users: `" + str(premium_count) + "`\n"
            "├ ⏱️ Report Interval: `" + str(self.report_interval) + "s`\n"
            "└ ⏰ Server Time: `" + current_time + "`\n\n"
            "🎯 *USE BELOW BUTTONS TO START OPERATIONS\\.*\n\n"
            "🔥 *MAINTAINED BY:* `" + escaped_dev_name + "` 🔥"
        )

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
                InlineKeyboardButton("⏱️ SET REPORT INTERVAL", callback_data="set_interval"),
                InlineKeyboardButton("📋 REPORT SETTINGS", callback_data="report_settings")
            ],
            [
                InlineKeyboardButton("🏆 VOUCH/PROOFS", url=self.vouch_channel),
                InlineKeyboardButton("🔄 UPDATE CHANNEL", url=self.update_channel)
            ],
            [
                InlineKeyboardButton("📺 TELEGRAM CHANNEL", url=self.telegram_channel)
            ],
            [
                InlineKeyboardButton("🔥 DEVELOPER 🔥", callback_data="developer_info")
            ],
            [
                InlineKeyboardButton("ℹ️ ABOUT", callback_data="about_info"),
                InlineKeyboardButton("❓ HELP", callback_data="help_info")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.safe_send_photo(
            chat_id=update.effective_chat.id,
            photo_url=self.welcome_image,
            caption=welcome_msg,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks with comprehensive error handling."""
        query = update.callback_query
        await query.answer()
        
        if not self.is_authorized(update):
            await query.message.reply_text("❌ Unauthorized access\\.", parse_mode='MarkdownV2')
            return

        data = query.data
        logger.info(f"Button pressed: {data} by user {query.from_user.id}")

        try:
            if data == "start_report":
                await self.show_report_menu(query, context)
            elif data == "view_status":
                await self.show_status(query, context)
            elif data == "generate_session":
                await self.show_session_generator(query, context)
            elif data == "manage_sessions":
                await self.show_session_manager(query, context)
            elif data == "how_to_add_sessions":
                await self.show_how_to_add_sessions(query, context)
            elif data == "premium_panel":
                await self.show_premium_panel(query, context)
            elif data == "set_interval":
                await self.show_interval_settings(query, context)
            elif data == "report_settings":
                await self.show_report_settings(query, context)
            elif data == "developer_info":
                await self.show_developer_info(query, context)
            elif data == "about_info":
                await self.show_about_info(query, context)
            elif data == "help_info":
                await self.show_help_info(query, context)
            elif data.startswith("session_type_"):
                await self.handle_session_type(query, context)
            elif data.startswith("report_reason_"):
                await self.handle_report_reason(query, context)
            elif data.startswith("interval_"):
                await self.handle_interval_selection(query, context)
            elif data == "confirm_report":
                await self.confirm_report(query, context)
            elif data == "cancel_report":
                await self.cancel_report(query, context)
            elif data == "back_to_main":
                await self.back_to_main(query, context)
            elif data == "stop_all_tasks":
                await self.stop_all_tasks(query, context)
            else:
                await query.message.reply_text("❌ Unknown command\\.", parse_mode='MarkdownV2')
            
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.message.reply_text("⚠️ An error occurred\\. Please try again\\.", parse_mode='MarkdownV2')

    async def show_session_generator(self, query, context):
        """Show session generator menu."""
        msg = (
            "🔥 *SESSION STRING GENERATOR* 🔥\n\n"
            "⚡ *CHOOSE THE STRING WHICH YOU WANT:*\n\n"
            "📱 Select your preferred session type below\\.\n\n"
            "🔒 *Real session generation with OTP verification*"
        )
        
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
            [InlineKeyboardButton("❌ CLOSE", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_status(self, query, context):
        """Show bot status with enhanced logging info."""
        session_count = len(self.sessions)
        available_sessions = len(self.get_available_sessions())
        task_count = len(self.active_tasks)
        premium_count = len([u for u, exp in self.premium_users.items() 
                           if datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > datetime.now()])

        # Get active tasks info with detailed logging
        active_tasks_info = ""
        for task_id, task_info in list(self.active_tasks.items())[:5]:
            status = task_info.get('status', 'running')
            success = task_info.get('success_count', 0)
            failed = task_info.get('failed_count', 0)
            sessions_used = len(task_info.get('sessions_used', []))
            task_short_id = task_id[:8] + "..."
            active_tasks_info += f"├ `{task_short_id}` \\- {status} {success}✅/{failed}❌ \$${sessions_used} sessions\$$\n"
        
        if not active_tasks_info:
            active_tasks_info = "└ No active tasks"

        # Get recent logs
        try:
            with open('bot.log', 'r') as f:
                logs = f.readlines()[-5:]  # Last 5 lines
            log_text = "\\n".join([self.escape_markdown(line.strip()) for line in logs])
        except:
            log_text = "No logs available"

        last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        escaped_updated = self.escape_markdown(last_updated)

        status_msg = (
            "📊 *BOT STATUS DASHBOARD*\n\n"
            "🔢 *STATISTICS:*\n"
            f"├ 📱 Total Sessions: `{session_count}`\n"
            f"├ 🟢 Available Sessions: `{available_sessions}`\n"
            f"├ 🚀 Running Tasks: `{task_count}`\n"
            f"├ 👑 Premium Users: `{premium_count}`\n"
            f"├ ⏱️ Report Interval: `{self.report_interval}s`\n"
            f"├ 🔄 Max Reports/Session: `{self.max_reports_per_session}`\n"
            f"└ 💾 System Status: `Online`\n\n"
            "🚀 *ACTIVE TASKS:*\n"
            f"{active_tasks_info}\n\n"
            "📋 *RECENT LOGS:*\n"
            f"\`\`\`\n{log_text}\n\`\`\`\n\n"
            f"⏰ *Last Updated:* `{escaped_updated}`"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="view_status")],
            [InlineKeyboardButton("⏹️ Stop All Tasks", callback_data="stop_all_tasks")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, status_msg, reply_markup, 'MarkdownV2')

    async def show_report_menu(self, query, context):
        """Show reporting menu and start conversation."""
        available_sessions = len(self.get_available_sessions())
        
        if available_sessions == 0:
            msg = (
                "⚠️ *NO SESSIONS AVAILABLE*\n\n"
                "❌ All sessions are in cooldown or no sessions added\\.\n\n"
                "⏳ *Session Cooldown:* `" + str(self.session_cooldown) + "s`\n"
                "➕ *Add more sessions or wait for cooldown\\.*"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        else:
            msg = (
                "📤 *MASS REPORTING SYSTEM*\n\n"
                "🟢 *Available Sessions:* `" + str(available_sessions) + "`\n"
                "⏱️ *Report Interval:* `" + str(self.report_interval) + "s`\n"
                "🔄 *Max Reports per Session:* `" + str(self.max_reports_per_session) + "`\n\n"
                "🎯 *Please send the channel/message link:*\n\n"
                "📋 *Supported formats:*\n"
                "├ `https://t\\.me/c/123456789`\n"
                "├ `https://t\\.me/username`\n"
                "├ `https://t\\.me/c/123456789/123`\n"
                "├ `https://t\\.me/username/123`\n"
                "└ `@username`\n\n"
                "💬 *Send the link as your next message\\.*"
            )
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_main")]]
            context.user_data['waiting_for'] = 'report_link'
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_session_manager(self, query, context):
        """Show session manager - Allow both admin and premium users."""
        session_count = len(self.sessions)
        available_count = len(self.get_available_sessions())
        user_type = "ADMIN" if self.is_admin_query(query) else "PREMIUM"
        
        msg = (
            "⚙️ *SESSION MANAGEMENT*\n\n"
            "📊 *Total Sessions:* `" + str(session_count) + "`\n"
            "🟢 *Available Sessions:* `" + str(available_count) + "`\n"
            "🔴 *In Cooldown:* `" + str(session_count - available_count) + "`\n\n"
            "📝 *Commands Available:*\n"
            "├ `/add_session session_string` \\- Add new session\n"
            "├ Sessions are automatically managed\n"
            "└ Cooldown: `" + str(self.session_cooldown) + "s` per session\n\n"
            "👤 *Access Level:* `" + user_type + "`\n\n"
            "🔧 *You can add sessions to improve reporting speed\\.*"
        )
        
        keyboard = [
            [InlineKeyboardButton("➕ How to Add Sessions", callback_data="how_to_add_sessions")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_how_to_add_sessions(self, query, context):
        """Show instructions for adding sessions."""
        msg = (
            "➕ *HOW TO ADD SESSION STRINGS*\n\n"
            "📝 *Step 1: Generate Session*\n"
            "├ Use the 'Generate Session' button\n"
            "├ Follow the OTP verification process\n"
            "└ Copy the generated session string\n\n"
            "📝 *Step 2: Add Session*\n"
            "├ Use command: `/add_session your_session_string`\n"
            "├ Paste the entire session string\n"
            "└ Session will be validated and added\n\n"
            "⚡ *Benefits of Multiple Sessions:*\n"
            "├ 🚀 Faster reporting speed\n"
            "├ 🛡️ Better flood protection\n"
            "├ 🔄 Automatic session rotation\n"
            "└ 📈 Higher success rates\n\n"
            "⚠️ *Important Notes:*\n"
            "├ Keep your sessions private\n"
            "├ Don't share session strings\n"
            "└ Each session = one Telegram account"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔥 Generate New Session", callback_data="generate_session")],
            [InlineKeyboardButton("🔙 Back to Sessions", callback_data="manage_sessions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_premium_panel(self, query, context):
        """Show premium panel."""
        if not self.is_admin_query(query):
            await self.safe_edit_message(query, "❌ Admin access required\\.", parse_mode='MarkdownV2')
            return
        
        premium_list = []
        current_time = datetime.now()
        
        for user_id, expiry in list(self.premium_users.items())[:10]:
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                if exp_date > current_time:
                    remaining = exp_date - current_time
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    premium_list.append("├ `" + user_id + "` \\- " + str(days) + "d " + str(hours) + "h left")
            except:
                continue
                
        premium_text = "\n".join(premium_list) if premium_list else "└ No active premium users"
        
        msg = (
            "👑 *PREMIUM USER MANAGEMENT*\n\n"
            "📊 *Current Premium Users:*\n"
            + premium_text + "\n\n"
            "➕ *To add premium user:*\n"
            "`/add_prm @username 7d`\n"
            "`/add_prm 123456789 30d`\n\n"
            "⏰ *Duration formats:*\n"
            "├ `1h` \\- 1 hour\n"
            "├ `1d` \\- 1 day\n"
            "├ `7d` \\- 7 days\n"
            "└ `30d` \\- 30 days"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_interval_settings(self, query, context):
        """Show interval settings menu."""
        msg = (
            "⏱️ *REPORT INTERVAL SETTINGS*\n\n"
            "📊 *Current Interval:* `" + str(self.report_interval) + " seconds`\n\n"
            "⚡ *Select new interval:*\n"
            "├ Faster intervals = Higher risk\n"
            "├ Slower intervals = Safer operation\n"
            "└ Recommended: 3\\-10 seconds\n\n"
            "🔧 *Choose your preferred interval:*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⚡ 1s", callback_data="interval_1"),
                InlineKeyboardButton("🚀 3s", callback_data="interval_3"),
                InlineKeyboardButton("⭐ 5s", callback_data="interval_5")
            ],
            [
                InlineKeyboardButton("🛡️ 10s", callback_data="interval_10"),
                InlineKeyboardButton("🐌 15s", callback_data="interval_15"),
                InlineKeyboardButton("🔒 30s", callback_data="interval_30")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_report_settings(self, query, context):
        """Show report settings menu."""
        msg = (
            "📋 *REPORT SETTINGS*\n\n"
            "⏱️ *Report Interval:* `" + str(self.report_interval) + "s`\n"
            "🔄 *Max Reports per Session:* `" + str(self.max_reports_per_session) + "`\n"
            "⏳ *Session Cooldown:* `" + str(self.session_cooldown) + "s`\n\n"
            "🎯 *Report Reasons Available:*\n"
            "├ 🚫 Spam\n"
            "├ ⚔️ Violence\n"
            "├ 🔞 Pornography\n"
            "└ 🎭 Fake Account\n\n"
            "⚙️ *Settings are optimized for safety*"
        )
        
        keyboard = [
            [InlineKeyboardButton("⏱️ Change Interval", callback_data="set_interval")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_developer_info(self, query, context):
        """Show developer info."""
        escaped_dev = self.escape_markdown(self.developer_username)
        escaped_dev_name = self.escape_markdown(self.developer_name)
        
        msg = (
            "🔥 *DEVELOPER INFORMATION* 🔥\n\n"
            "👨‍💻 *Created by:* `" + escaped_dev_name + "`\n"
            "🚀 *Version:* `3\\.0\\.0`\n"
            "📅 *Last Updated:* `2025\\-07\\-31`\n\n"
            "💼 *Skills:*\n"
            "├ 🐍 Python Development\n"
            "├ 🤖 Telegram Bot Creation\n"
            "├ 🔧 API Integration\n"
            "├ 📊 Mass Reporting Systems\n"
            "└ 🎨 UI/UX Design\n\n"
            "📞 *Contact:* @" + escaped_dev
        )
        
        keyboard = [
            [InlineKeyboardButton("💬 Contact Developer", url=f"https://t.me/{self.developer_username}")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_about_info(self, query, context):
        """Show about info."""
        escaped_dev_name = self.escape_markdown(self.developer_name)
        
        msg = (
            "ℹ️ *ABOUT MASS REPORTER BOT*\n\n"
            "🤖 *Advanced Telegram Automation & Session Management*\n\n"
            "✨ *Features:*\n"
            "├ 📤 Mass reporting automation\n"
            "├ 🔑 Session string generation\n"
            "├ 👑 Premium user management\n"
            "├ 📊 Real\\-time monitoring\n"
            "├ 🔧 Multi\\-session support\n"
            "└ 📋 Advanced logging\n\n"
            "🔥 *MAINTAINED BY:* `" + escaped_dev_name + "` 🔥"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def show_help_info(self, query, context):
        """Show help info."""
        msg = (
            "❓ *HELP & COMMANDS*\n\n"
            "📋 *Available Commands:*\n"
            "├ `/start` \\- Show main menu\n"
            "├ `/status` \\- View bot status\n"
            "├ `/help` \\- Show this help\n\n"
            "💡 *Usage Tips:*\n"
            "├ Use buttons for easy navigation\n"
            "├ Follow prompts for session generation\n"
            "└ Contact support for issues\n\n"
            "🆘 *Need more help?* Contact vouch channel\\!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏆 Vouch Channel", url=self.vouch_channel)],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def handle_session_type(self, query, context):
        """Handle session type selection."""
        session_type = query.data.replace("session_type_", "")
        context.user_data['session_type'] = session_type
        context.user_data['waiting_for'] = 'api_id'
        
        session_type_display = session_type.upper().replace('_', ' ')
        
        msg = (
            "🚀 *STARTING " + session_type_display + " SESSION GENERATOR*\n\n"
            "📝 *STEP 1: SEND YOUR API\\_ID*\n\n"
            "💡 Get your API credentials from: `my\\.telegram\\.org`\n\n"
            "⚠️ *Send your API\\_ID as your next message\\.*"
        )
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def handle_report_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle report link input with enhanced validation."""
        link = update.message.text.strip()
        
        # Enhanced link validation
        patterns = [
            r'^https?://t\.me/c/(\d+)(/(\d+))?$',  # Private channel
            r'^https?://t\.me/([a-zA-Z0-9_]+)(/(\d+))?$',  # Public channel
            r'^@([a-zA-Z0-9_]+)$',  # Username only
        ]
        
        match = None
        for pattern in patterns:
            match = re.match(pattern, link)
            if match:
                break
        
        if not match:
            error_msg = (
                "⚠️ *INVALID LINK FORMAT\\!*\n\n"
                "📋 *Please use:*\n"
                "├ `https://t\\.me/c/123456789`\n"
                "├ `https://t\\.me/username`\n"
                "├ `https://t\\.me/c/123456789/123`\n"
                "├ `https://t\\.me/username/123`\n"
                "└ `@username`\n\n"
                "🔄 *Try again with correct format\\.*"
            )
            await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
            return

        # Parse link details
        if '/c/' in link:
            is_private = True
            chat_id = match.group(1)
            msg_id = int(match.group(3)) if match.group(3) else None
        elif link.startswith('@'):
            is_private = False
            chat_id = match.group(1)
            msg_id = None
        else:
            is_private = False
            chat_id = match.group(1)
            msg_id = int(match.group(3)) if match.group(3) else None

        context.user_data['report_data'] = {
            'chat_id': chat_id,
            'msg_id': msg_id,
            'is_private': is_private,
            'link': link
        }

        available_sessions = len(self.get_available_sessions())
        estimated_time = available_sessions * self.report_interval

        escaped_chat_id = self.escape_markdown(chat_id)
        
        confirm_msg = (
            "✅ *LINK PARSED SUCCESSFULLY\\!*\n\n"
            "📌 *Target Details:*\n"
            "├ Chat: `" + escaped_chat_id + "`\n"
        )
        
        if msg_id:
            confirm_msg += "├ Message ID: `" + str(msg_id) + "`\n"
        
        confirm_msg += (
            "├ Type: `" + ('Private' if is_private else 'Public') + "`\n"
            "├ Available Sessions: `" + str(available_sessions) + "`\n"
            "├ Report Interval: `" + str(self.report_interval) + "s`\n"
            "└ Estimated Time: `" + str(estimated_time) + "s`\n\n"
            "🎯 *Select report reason:*"
        )

        keyboard = [
            [
                InlineKeyboardButton("🚫 SPAM", callback_data="report_reason_spam"),
                InlineKeyboardButton("⚔️ VIOLENCE", callback_data="report_reason_violence")
            ],
            [
                InlineKeyboardButton("🔞 PORNOGRAPHY", callback_data="report_reason_porn"),
                InlineKeyboardButton("🎭 FAKE", callback_data="report_reason_fake")
            ],
            [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(confirm_msg, reply_markup=reply_markup, parse_mode='MarkdownV2')
        context.user_data['waiting_for'] = 'report_reason'

    async def handle_report_reason(self, query, context):
        """Handle report reason selection."""
        reason = query.data.replace("report_reason_", "")
        context.user_data['report_reason'] = reason
        
        report_data = context.user_data.get('report_data', {})
        available_sessions = len(self.get_available_sessions())
        
        reason_map = {
            'spam': '🚫 SPAM',
            'violence': '⚔️ VIOLENCE', 
            'porn': '🔞 PORNOGRAPHY',
            'fake': '🎭 FAKE ACCOUNT'
        }
        
        escaped_chat_id = self.escape_markdown(report_data.get('chat_id', 'Unknown'))
        
        final_confirm_msg = (
            "🚀 *READY TO START MASS REPORTING\\!*\n\n"
            "🎯 *Target:* `" + escaped_chat_id + "`\n"
            "📋 *Reason:* " + reason_map.get(reason, 'SPAM') + "\n"
            "📱 *Sessions:* `" + str(available_sessions) + "`\n"
            "⏱️ *Interval:* `" + str(self.report_interval) + "s`\n"
            "🔄 *Max per Session:* `" + str(self.max_reports_per_session) + "`\n\n"
            "⚠️ *WARNING:*\n"
            "├ This action cannot be undone\n"
            "├ Use responsibly\n"
            "└ Follow Telegram ToS\n\n"
            "✅ *Confirm to start reporting\\?*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ CONFIRM & START", callback_data="confirm_report"),
                InlineKeyboardButton("❌ CANCEL", callback_data="cancel_report")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.safe_edit_message(query, final_confirm_msg, reply_markup, 'MarkdownV2')

    async def confirm_report(self, query, context):
        """Confirm and start reporting."""
        report_data = context.user_data.get('report_data')
        report_reason = context.user_data.get('report_reason', 'spam')
        
        if not report_data:
            await self.safe_edit_message(query, "⚠️ *Error: No report data found\\.*", parse_mode='MarkdownV2')
            return

        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Start reporting task
        self.active_tasks[task_id] = {
            'chat_id': report_data['chat_id'],
            'msg_id': report_data['msg_id'],
            'is_private': report_data['is_private'],
            'reason': report_reason,
            'status': 'starting',
            'success_count': 0,
            'failed_count': 0,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sessions_used': []
        }
        
        # Start the reporting process in background
        asyncio.create_task(self.process_reporting(task_id))
        
        task_short_id = task_id[:8] + "..."
        escaped_chat_id = self.escape_markdown(report_data['chat_id'])
        
        success_msg = (
            "🚀 *MASS REPORTING STARTED\\!*\n\n"
            "🆔 *Task ID:* `" + task_short_id + "`\n"
            "🎯 *Target:* `" + escaped_chat_id + "`\n"
            "📊 *Sessions:* `" + str(len(self.get_available_sessions())) + "`\n"
            "⏱️ *Interval:* `" + str(self.report_interval) + "s`\n\n"
            "⏳ *Processing\\.\\.\\. Check status with /status*\n\n"
            "📊 *Real\\-time updates will be sent\\.*"
        )
        
        await self.safe_edit_message(query, success_msg, parse_mode='MarkdownV2')
        
        # Clear user data
        context.user_data.clear()

    async def handle_interval_selection(self, query, context):
        """Handle interval selection."""
        interval = int(query.data.replace("interval_", ""))
        self.report_interval = interval
        
        success_msg = (
            "✅ *INTERVAL UPDATED SUCCESSFULLY\\!*\n\n"
            "⏱️ *New Interval:* `" + str(interval) + " seconds`\n\n"
            "🔄 *This will apply to all new reporting tasks\\.*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, success_msg, reply_markup, 'MarkdownV2')

    async def stop_all_tasks(self, query, context):
        """Stop all active tasks."""
        if not self.is_admin_query(query):
            await self.safe_edit_message(query, "❌ Admin access required\\.", parse_mode='MarkdownV2')
            return
        
        stopped_count = len(self.active_tasks)
        self.active_tasks.clear()
        
        msg = (
            "⏹️ *ALL TASKS STOPPED\\!*\n\n"
            "📊 *Stopped Tasks:* `" + str(stopped_count) + "`\n\n"
            "✅ *All reporting operations have been terminated\\.*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.safe_edit_message(query, msg, reply_markup, 'MarkdownV2')

    async def back_to_main(self, query, context):
        """Go back to main menu."""
        context.user_data.clear()  # Clear any ongoing conversations
        
        # Create a mock update for the start method
        class MockUpdate:
            def __init__(self, query):
                self.effective_user = query.from_user
                self.effective_chat = query.message.chat
                self.message = query.message
        
        mock_update = MockUpdate(query)
        await self.start(mock_update, context)

    async def cancel_report(self, query, context):
        """Cancel reporting."""
        context.user_data.clear()
        await self.safe_edit_message(query, "❌ *Reporting cancelled\\.*", parse_mode='MarkdownV2')

    async def handle_api_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle API ID input."""
        api_id = update.message.text.strip()
        
        try:
            int(api_id)
            context.user_data['api_id'] = api_id
            context.user_data['waiting_for'] = 'api_hash'
            
            msg = (
                "✅ *API\\_ID RECEIVED:* `" + api_id + "`\n\n"
                "📝 *STEP 2: SEND YOUR API\\_HASH*\n\n"
                "⚠️ *Send your API\\_HASH as your next message\\.*"
            )
            await update.message.reply_text(msg, parse_mode='MarkdownV2')
        except ValueError:
            await update.message.reply_text("❌ *Invalid API\\_ID\\. Please send a valid number\\.*", parse_mode='MarkdownV2')

    async def handle_api_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle API Hash input."""
        api_hash = update.message.text.strip()
        
        if len(api_hash) == 32:
            context.user_data['api_hash'] = api_hash
            context.user_data['waiting_for'] = 'phone'
            
            session_type = context.user_data.get('session_type', 'telethon')
            
            if 'bot' in session_type:
                msg = (
                    "✅ *API\\_HASH RECEIVED\\!*\n\n"
                    "📝 *STEP 3: SEND YOUR BOT\\_TOKEN*\n\n"
                    "📋 *EXAMPLE:* `5432198765:abcdanonymouserabaapol`\n\n"
                    "⚠️ *Send your bot token as your next message\\.*"
                )
            else:
                msg = (
                    "✅ *API\\_HASH RECEIVED\\!*\n\n"
                    "📝 *STEP 3: SEND YOUR PHONE NUMBER*\n\n"
                    "📋 *EXAMPLE:* `+1234567890`\n\n"
                    "⚠️ *Send your phone number as your next message\\.*"
                )
            
            await update.message.reply_text(msg, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("❌ *Invalid API\\_HASH\\. Must be 32 characters\\.*", parse_mode='MarkdownV2')

    async def handle_phone_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number/bot token input."""
        phone_or_token = update.message.text.strip()
        
        session_type = context.user_data.get('session_type', 'telethon')
        api_id = context.user_data.get('api_id')
        api_hash = context.user_data.get('api_hash')
        
        if 'bot' in session_type:
            # Handle bot token
            await self.generate_bot_session(update, context, api_id, api_hash, phone_or_token, session_type)
        else:
            # Handle phone number for user session
            context.user_data['phone'] = phone_or_token
            context.user_data['waiting_for'] = 'otp'
            
            generating_msg = (
                "📱 *PHONE NUMBER RECEIVED:* `" + self.escape_markdown(phone_or_token) + "`\n\n"
                "🚀 *SENDING OTP\\.\\.\\.*\n\n"
                "⏳ *Please wait while we send the verification code\\.*"
            )
            await update.message.reply_text(generating_msg, parse_mode='MarkdownV2')
            
            # Send OTP
            await self.send_otp(update, context, api_id, api_hash, phone_or_token, session_type)

    async def send_otp(self, update: Update, context: ContextTypes.DEFAULT_TYPE, api_id: str, api_hash: str, phone: str, session_type: str):
        """Send OTP for session generation."""
        try:
            user_id = str(update.effective_user.id)
            
            if session_type == 'telethon':
                # Telethon session generation
                client = TelegramClient(f'temp_{user_id}', int(api_id), api_hash)
                await client.connect()
                
                result = await client.send_code_request(phone)
                context.user_data['phone_code_hash'] = result.phone_code_hash
                context.user_data['temp_client'] = client
                
                success_msg = (
                    "✅ *OTP SENT SUCCESSFULLY\\!*\n\n"
                    "📱 *Check your Telegram app for the verification code\\.*\n\n"
                    "📝 *STEP 4: SEND THE OTP CODE*\n\n"
                    "⚠️ *Send the 5\\-digit code as your next message\\.*"
                )
                
            else:
                # Pyrogram session generation
                app = Client(f'temp_{user_id}', api_id=int(api_id), api_hash=api_hash)
                await app.connect()
                
                sent_code = await app.send_code(phone)
                context.user_data['phone_code_hash'] = sent_code.phone_code_hash
                context.user_data['temp_client'] = app
                
                success_msg = (
                    "✅ *OTP SENT SUCCESSFULLY\\!*\n\n"
                    "📱 *Check your Telegram app for the verification code\\.*\n\n"
                    "📝 *STEP 4: SEND THE OTP CODE*\n\n"
                    "⚠️ *Send the 5\\-digit code as your next message\\.*"
                )
            
            await update.message.reply_text(success_msg, parse_mode='MarkdownV2')
            
        except Exception as e:
            error_msg = (
                "❌ *FAILED TO SEND OTP\\!*\n\n"
                "📝 *Error:* `" + self.escape_markdown(str(e)) + "`\n\n"
                "🔄 *Please check your phone number and try again\\.*"
            )
            await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
            context.user_data.clear()

    async def handle_otp_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle OTP input and generate session."""
        otp = update.message.text.strip()
        
        if not otp.isdigit() or len(otp) != 5:
            await update.message.reply_text("❌ *Invalid OTP\\. Please send a 5\\-digit code\\.*", parse_mode='MarkdownV2')
            return
        
        session_type = context.user_data.get('session_type', 'telethon')
        phone = context.user_data.get('phone')
        phone_code_hash = context.user_data.get('phone_code_hash')
        temp_client = context.user_data.get('temp_client')
        
        generating_msg = (
            "🔐 *VERIFYING OTP AND GENERATING SESSION\\.\\.\\.*\n\n"
            "⏳ *This may take a few moments\\.*"
        )
        await update.message.reply_text(generating_msg, parse_mode='MarkdownV2')
        
        try:
            if session_type == 'telethon':
                await temp_client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
                session_string = temp_client.session.save()
                await temp_client.disconnect()
                
            else:  # pyrogram
                await temp_client.sign_in(phone, phone_code_hash, otp)
                session_string = await temp_client.export_session_string()
                await temp_client.disconnect()
            
            # Save session string to user's saved messages
            await self.save_session_to_user(update, session_string, session_type)
            
            escaped_session = self.escape_markdown(session_string)
            
            success_msg = (
                "✅ *SESSION GENERATED SUCCESSFULLY\\!*\n\n"
                "🔑 *Session Type:* `" + session_type.upper() + "`\n\n"
                "📋 *Session String:*\n`" + escaped_session + "`\n\n"
                "💾 *Session has been saved to your Saved Messages\\!*\n\n"
                "⚠️ *IMPORTANT:*\n"
                "├ Keep your session string private\n"
                "├ Don't share it with anyone\n"
                "└ Store it securely\n\n"
                "🎉 *You can now use this session for automation\\!*"
            )
            await update.message.reply_text(success_msg, parse_mode='MarkdownV2')
            
        except SessionPasswordNeeded:
            await update.message.reply_text(
                "🔐 *Two\\-factor authentication detected\\!*\n\n"
                "📝 *Please send your 2FA password as your next message\\.*",
                parse_mode='MarkdownV2'
            )
            context.user_data['waiting_for'] = '2fa'
            return
            
        except Exception as e:
            escaped_error = self.escape_markdown(str(e))
            error_msg = (
                "❌ *SESSION GENERATION FAILED\\!*\n\n"
                "📝 *Error:* `" + escaped_error + "`\n\n"
                "🔄 *Please try again with correct OTP\\.*"
            )
            await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
        
        # Clear user data
        context.user_data.clear()

    async def save_session_to_user(self, update: Update, session_string: str, session_type: str):
        """Save session string to user's saved messages."""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            formatted_message = (
                f"🔥 **SESSION STRING GENERATED** 🔥\n\n"
                f"👤 **User:** @{username}\n"
                f"🔑 **Type:** {session_type.upper()}\n"
                f"📅 **Generated:** {timestamp}\n\n"
                f"**Session String:**\n`{session_string}`\n\n"
                f"⚠️ **Keep this private and secure!**\n"
                f"🤖 **Generated by:** @{self.developer_username}"
            )
            
            await self.app.bot.send_message(
                chat_id=user_id,
                text=formatted_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Failed to save session to user: {e}")

    async def generate_bot_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE, api_id: str, api_hash: str, bot_token: str, session_type: str):
        """Generate bot session string."""
        generating_msg = (
            "🤖 *GENERATING BOT SESSION\\.\\.\\.*\n\n"
            "⏳ *Please wait while we generate your bot session\\.*"
        )
        await update.message.reply_text(generating_msg, parse_mode='MarkdownV2')
        
        try:
            if session_type == 'telethon_bot':
                client = TelegramClient('temp_bot', int(api_id), api_hash)
                await client.start(bot_token=bot_token)
                session_string = client.session.save()
                await client.disconnect()
                
            else:  # pyrogram_bot
                app = Client('temp_bot', api_id=int(api_id), api_hash=api_hash, bot_token=bot_token)
                await app.start()
                session_string = await app.export_session_string()
                await app.stop()
            
            # Save session string to user's saved messages
            await self.save_session_to_user(update, session_string, session_type)
            
            escaped_session = self.escape_markdown(session_string)
            
            success_msg = (
                "✅ *BOT SESSION GENERATED SUCCESSFULLY\\!*\n\n"
                "🔑 *Session Type:* `" + session_type.upper() + "`\n\n"
                "📋 *Session String:*\n`" + escaped_session + "`\n\n"
                "💾 *Session has been saved to your Saved Messages\\!*\n\n"
                "⚠️ *IMPORTANT:*\n"
                "├ Keep your session string private\n"
                "├ Don't share it with anyone\n"
                "└ Store it securely\n\n"
                "🎉 *You can now use this bot session for automation\\!*"
            )
            await update.message.reply_text(success_msg, parse_mode='MarkdownV2')
            
        except Exception as e:
            escaped_error = self.escape_markdown(str(e))
            error_msg = (
                "❌ *BOT SESSION GENERATION FAILED\\!*\n\n"
                "📝 *Error:* `" + escaped_error + "`\n\n"
                "🔄 *Please check your bot token and try again\\.*"
            )
            await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
        
        # Clear user data
        context.user_data.clear()

    async def process_reporting(self, task_id: str):
        """Enhanced reporting process with detailed logging and session rotation."""
        task = self.active_tasks.get(task_id)
        if not task:
            return
        
        logger.info(f"🚀 Starting reporting task {task_id}")
        task['status'] = 'running'
        
        available_sessions = self.get_available_sessions()
        
        if not available_sessions:
            task['status'] = 'failed'
            task['error'] = 'No available sessions'
            logger.error(f"❌ Task {task_id} failed: No available sessions")
            return
        
        # Check if API credentials are available
        if not self.api_id or not self.api_hash:
            task['status'] = 'failed'
            task['error'] = 'API credentials not configured'
            logger.error(f"❌ Task {task_id} failed: API credentials missing")
            return
        
        # Reason mapping
        reason_map = {
            'spam': InputReportReasonSpam(),
            'violence': InputReportReasonViolence(),
            'porn': InputReportReasonPornography(),
            'fake': InputReportReasonSpam()
        }
        
        report_reason = reason_map.get(task['reason'], InputReportReasonSpam())
        
        # Enhanced logging for reporting process
        logger.info(f"📊 Task {task_id} - Target: {task['chat_id']}, Sessions: {len(available_sessions)}, Reason: {task['reason']}")
        
        session_rotation_count = 0
        
        for i, session_string in enumerate(available_sessions):
            if task['status'] != 'running':
                logger.info(f"⏹️ Task {task_id} stopped by user")
                break
                
            try:
                logger.info(f"🔄 Task {task_id} - Using session {i+1}/{len(available_sessions)}")
                
                # Create client
                client = TelegramClient(session_string, self.api_id, self.api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    logger.warning(f"⚠️ Task {task_id} - Session {i+1} not authorized, skipping")
                    task['failed_count'] += 1
                    continue
                
                # Get target entity
                try:
                    if task['is_private']:
                        entity = await client.get_entity(int(f"-100{task['chat_id']}"))
                        logger.info(f"🎯 Task {task_id} - Targeting private channel: {task['chat_id']}")
                    else:
                        entity = await client.get_entity(task['chat_id'])
                        logger.info(f"🎯 Task {task_id} - Targeting public entity: {task['chat_id']}")
                except Exception as e:
                    logger.error(f"❌ Task {task_id} - Failed to get entity: {e}")
                    task['failed_count'] += 1
                    continue
                
                # Perform report
                try:
                    if task['msg_id']:
                        # Report specific message
                        await client(ReportRequest(
                            peer=entity,
                            id=[task['msg_id']],
                            reason=report_reason
                        ))
                        logger.info(f"✅ Task {task_id} - Reported message {task['msg_id']} using session {i+1}")
                    else:
                        # Report the channel/user
                        await client(ReportRequest(
                            peer=entity,
                            id=[1],  # Dummy message ID for channel reports
                            reason=report_reason
                        ))
                        logger.info(f"✅ Task {task_id} - Reported entity using session {i+1}")
                    
                    task['success_count'] += 1
                    task['sessions_used'].append(session_string)
                    
                    # Update session usage
                    self.session_usage[session_string] = {
                        'last_used': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'reports_count': self.session_usage.get(session_string, {}).get('reports_count', 0) + 1
                    }
                    
                    logger.info(f"📈 Task {task_id} - Success: {task['success_count']}, Failed: {task['failed_count']}")
                    
                except FloodWaitError as e:
                    logger.warning(f"🚫 Task {task_id} - Flood wait {e.seconds}s for session {i+1}")
                    task['failed_count'] += 1
                    # Put session in longer cooldown
                    self.session_usage[session_string] = {
                        'last_used': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'flood_wait_until': (datetime.now() + timedelta(seconds=e.seconds)).strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                except Exception as e:
                    logger.error(f"❌ Task {task_id} - Report failed for session {i+1}: {e}")
                    task['failed_count'] += 1
                
                await client.disconnect()
                
                # Session rotation logic
                session_rotation_count += 1
                if session_rotation_count % 5 == 0:  # Rotate every 5 sessions
                    logger.info(f"🔄 Task {task_id} - Session rotation break (used {session_rotation_count} sessions)")
                    await asyncio.sleep(30)  # 30 second break for rotation
                
                # Check if reached max reports per session
                if task['success_count'] >= self.max_reports_per_session * len(available_sessions):
                    logger.info(f"🎯 Task {task_id} - Reached maximum reports limit")
                    break
                
                # Wait between reports
                logger.info(f"⏱️ Task {task_id} - Waiting {self.report_interval}s before next report")
                await asyncio.sleep(self.report_interval)
                
            except Exception as e:
                logger.error(f"❌ Task {task_id} - Session {i+1} error: {e}")
                task['failed_count'] += 1
                continue
        
        # Mark task as completed
        task['status'] = 'completed'
        task['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"🏁 Task {task_id} completed - Success: {task['success_count']}, Failed: {task['failed_count']}, Sessions used: {len(task['sessions_used'])}")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages based on conversation state."""
        if not self.is_authorized(update):
            return

        waiting_for = context.user_data.get('waiting_for')
        
        try:
            if waiting_for == 'report_link':
                await self.handle_report_link(update, context)
            elif waiting_for == 'api_id':
                await self.handle_api_id(update, context)
            elif waiting_for == 'api_hash':
                await self.handle_api_hash(update, context)
            elif waiting_for == 'phone':
                await self.handle_phone_input(update, context)
            elif waiting_for == 'otp':
                await self.handle_otp_input(update, context)
            else:
                # No active conversation, show help
                help_msg = (
                    "💡 *Use /start to see the main menu*\n\n"
                    "📋 *Available commands:*\n"
                    "├ `/start` \\- Main menu\n"
                    "├ `/status` \\- Bot status\n"
                    "└ `/help` \\- Show help"
                )
                await update.message.reply_text(help_msg, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            await update.message.reply_text("⚠️ An error occurred\\. Please try /start", parse_mode='MarkdownV2')

    async def add_premium_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add premium user command."""
        if not self.is_admin(update):
            await update.message.reply_text("❌ *Admin access required\\.*", parse_mode='MarkdownV2')
            return

        if len(context.args) != 2:
            help_msg = (
                "📋 *USAGE:*\n\n"
                "`/add_prm @username 7d`\n"
                "`/add_prm 123456789 30d`\n\n"
                "⏰ *Duration formats:*\n"
                "├ `1h` \\- 1 hour\n"
                "├ `1d` \\- 1 day\n"
                "├ `7d` \\- 7 days\n"
                "└ `30d` \\- 30 days"
            )
            await update.message.reply_text(help_msg, parse_mode='MarkdownV2')
            return

        user_input, duration_str = context.args
        
        # Parse duration
        try:
            if duration_str.endswith('h'):
                hours = int(duration_str[:-1])
                expiry = datetime.now() + timedelta(hours=hours)
            elif duration_str.endswith('d'):
                days = int(duration_str[:-1])
                expiry = datetime.now() + timedelta(days=days)
            else:
                raise ValueError("Invalid duration format")
        except ValueError:
            await update.message.reply_text("⚠️ *Invalid duration format\\.*", parse_mode='MarkdownV2')
            return

        # Get user ID (simplified - in production you'd resolve username)
        if user_input.startswith('@'):
            user_id = user_input[1:]
        else:
            try:
                user_id = str(int(user_input))
            except ValueError:
                await update.message.reply_text("⚠️ *Invalid user ID\\.*", parse_mode='MarkdownV2')
                return

        # Add premium user
        self.premium_users[user_id] = expiry.strftime("%Y-%m-%d %H:%M:%S")
        self.save_premium_users()
        
        escaped_user = self.escape_markdown(user_input)
        expiry_str = expiry.strftime('%Y-%m-%d %H:%M:%S')
        escaped_expiry = self.escape_markdown(expiry_str)
        escaped_duration = self.escape_markdown(duration_str)
        
        success_msg = (
            "👑 *PREMIUM USER ADDED\\!*\n\n"
            "👤 *User:* `" + escaped_user + "`\n"
            "⏰ *Expires:* `" + escaped_expiry + "`\n"
            "📅 *Duration:* `" + escaped_duration + "`"
        )
        
        await update.message.reply_text(success_msg, parse_mode='MarkdownV2')

    async def add_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add session command - Allow both admin and premium users."""
        if not self.is_authorized(update):
            await update.message.reply_text("❌ *Unauthorized access\\. Premium users only\\.*", parse_mode='MarkdownV2')
            return

        if not context.args:
            help_msg = (
                "📋 *USAGE:*\n\n"
                "`/add_session session_string_here`\n\n"
                "🔑 *Add one session string at a time\\.*\n\n"
                "💡 *You can add multiple sessions for better performance\\.*"
            )
            await update.message.reply_text(help_msg, parse_mode='MarkdownV2')
            return

        session_string = ' '.join(context.args)
        
        if session_string in self.sessions:
            await update.message.reply_text("⚠️ *Session already exists\\.*", parse_mode='MarkdownV2')
            return

        # Validate session string format (basic check)
        if len(session_string) < 50:
            await update.message.reply_text("⚠️ *Invalid session string format\\. Too short\\.*", parse_mode='MarkdownV2')
            return

        # Add session
        self.sessions.append(session_string)
        self.save_sessions()
        
        user_type = "ADMIN" if self.is_admin(update) else "PREMIUM"
        username = update.effective_user.first_name or "User"
        
        success_msg = (
            "✅ *SESSION ADDED SUCCESSFULLY\\!*\n\n"
            "👤 *Added by:* `" + self.escape_markdown(username) + "` \$$" + user_type + "\$$\n"
            "📊 *Total Sessions:* `" + str(len(self.sessions)) + "`\n"
            "🟢 *Available Sessions:* `" + str(len(self.get_available_sessions())) + "`\n\n"
            "🎉 *Your session is now ready for reporting\\!*"
        )
        
        await update.message.reply_text(success_msg, parse_mode='MarkdownV2')
        
        # Log the session addition
        logger.info(f"Session added by {username} ({user_type}) - Total sessions: {len(self.sessions)}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Status command."""
        if not self.is_authorized(update):
            await update.message.reply_text("❌ *Unauthorized access\\.*", parse_mode='MarkdownV2')
            return
            
        session_count = len(self.sessions)
        available_sessions = len(self.get_available_sessions())
        task_count = len(self.active_tasks)
        premium_count = len([u for u, exp in self.premium_users.items() 
                           if datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > datetime.now()])

        status_msg = (
            "📊 *BOT STATUS*\n\n"
            "📱 *Sessions:* `" + str(session_count) + "`\n"
            "🟢 *Available:* `" + str(available_sessions) + "`\n"
            "🚀 *Tasks:* `" + str(task_count) + "`\n"
            "👑 *Premium:* `" + str(premium_count) + "`\n"
            "⏰ *Time:* `" + datetime.now().strftime('%H:%M:%S') + "`"
        )
        
        await update.message.reply_text(status_msg, parse_mode='MarkdownV2')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command."""
        is_admin = self.is_admin(update)
        
        help_msg = (
            "❓ *HELP & COMMANDS*\n\n"
            "📋 *Available Commands:*\n"
            "├ `/start` \\- Show main menu\n"
            "├ `/status` \\- View bot status\n"
            "├ `/help` \\- Show this help\n"
            "├ `/add_session` \\- Add session string\n"
        )
        
        if is_admin:
            help_msg += (
                "\n👑 *Admin Commands:*\n"
                "└ `/add_prm` \\- Add premium user\n"
            )
        
        help_msg += "\n💡 *Use /start for the interactive menu\\!*"
        
        await update.message.reply_text(help_msg, parse_mode='MarkdownV2')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler."""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ *An error occurred\\. Please try /start*",
                    parse_mode='MarkdownV2'
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    def run(self):
        """Run the bot."""
        self.app = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('status', self.status_command))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('add_prm', self.add_premium_command))
        self.app.add_handler(CommandHandler('add_session', self.add_session_command))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        
        # Add error handler
        self.app.add_error_handler(self.error_handler)

        logger.info("🚀 Mass Reporter Bot started successfully!")
        self.app.run_polling()

if __name__ == "__main__":
    try:
        bot = MassReporterBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Bot startup failed: {e}")
