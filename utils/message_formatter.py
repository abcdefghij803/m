from datetime import datetime
from typing import Dict, List

class MessageFormatter:
    """Format messages with consistent styling for the bot."""
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def format_session_generation_start(session_type: str) -> str:
        """Format session generation start message."""
        return (
            f"🚀 **TRYING TO START {session_type.upper().replace('_', ' ')} SESSION GENERATOR\\.\\.\\.**\n\n"
            "📝 **SEND YOUR API\\_ID TO PROCEED:**\n\n"
            "💡 Get your API credentials from: `my\\.telegram\\.org`\n\n"
            "⚠️ **Note:** Your credentials are processed securely and not stored\\."
        )
    
    @staticmethod
    def format_api_received(api_type: str, value: str) -> str:
        """Format API credential received message."""
        masked_value = f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}" if len(value) > 8 else value
        
        if api_type == "api_id":
            return (
                f"✅ **API\\_ID RECEIVED:** `{masked_value}`\n\n"
                "📝 **NOW SEND YOUR API\\_HASH TO CONTINUE:**\n\n"
                "🔒 **Your API\\_ID is securely stored for this session\\.**"
            )
        elif api_type == "api_hash":
            return (
                f"✅ **API\\_HASH RECEIVED:** `{masked_value}`\n\n"
                "🔑 **PLEASE SEND YOUR BOT\\_TOKEN TO CONTINUE:**\n\n"
                "📋 **EXAMPLE:** `5432198765:abcdanonymouserabaapol`\n\n"
                "💡 **For user session, send your phone number instead\\.**"
            )
    
    @staticmethod
    def format_session_success(session_type: str, session_string: str) -> str:
        """Format successful session generation message."""
        masked_session = f"{session_string[:20]}...{session_string[-20:]}" if len(session_string) > 40 else session_string
        
        return (
            "✅ **SESSION GENERATED SUCCESSFULLY\\!**\n\n"
            f"🔑 **Session Type:** `{session_type.upper()}`\n"
            f"📋 **Session String:**\n`{MessageFormatter.escape_markdown(masked_session)}`\n\n"
            "⚠️ **IMPORTANT:**\n"
            "├ Keep your session string private\n"
            "├ Don't share it with anyone\n"
            "└ Store it securely\n\n"
            "🎉 **You can now use this session for automation\\!**"
        )
    
    @staticmethod
    def format_reporting_status(task_id: str, target: str, sessions_count: int, success_count: int = 0, failed_count: int = 0) -> str:
        """Format reporting status message."""
        return (
            "🚀 **MASS REPORTING IN PROGRESS**\n\n"
            f"🆔 **Task ID:** `{task_id}`\n"
            f"🎯 **Target:** `{MessageFormatter.escape_markdown(target)}`\n"
            f"📊 **Sessions Used:** `{sessions_count}`\n"
            f"✅ **Successful Reports:** `{success_count}`\n"
            f"❌ **Failed Reports:** `{failed_count}`\n\n"
            "⏳ **Status will update automatically\\.\\.\\.**"
        )
    
    @staticmethod
    def format_error_message(error_type: str, details: str = None) -> str:
        """Format error messages consistently."""
        base_msg = "❌ **ERROR OCCURRED**\n\n"
        
        error_messages = {
            "unauthorized": "🚫 **Unauthorized access\\.**\n💎 Contact admin for premium access\\.",
            "invalid_link": "⚠️ **Invalid link format\\.**\n📋 Please use supported formats\\.",
            "no_sessions": "📱 **No active sessions available\\.**\n➕ Add sessions first\\.",
            "api_error": "🔧 **API Error\\.**\n🔄 Please try again later\\.",
            "session_error": "🔑 **Session generation failed\\.**\n✅ Check your credentials\\."
        }
        
        error_msg = error_messages.get(error_type, "⚠️ **Unknown error occurred\\.**")
        
        if details:
            error_msg += f"\n\n📝 **Details:** `{MessageFormatter.escape_markdown(details)}`"
            
        return base_msg + error_msg
