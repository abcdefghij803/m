from telegram import Update
from telegram.ext import ContextTypes
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

ADD_SESSION_COUNT, ADD_SESSION_INPUT, ADD_PREMIUM = range(3)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current bot status and active tasks."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return

    reporting_service = bot.reporting_service
    session_manager = bot.session_manager
    status_message = (
        f"Bot Status:\n"
        f"Active Sessions: {len(session_manager.get_active_sessions())}\n"
        f"Active Tasks: {len(reporting_service.active_tasks)}\n\n"
        f"Tasks:\n"
    )
    for task_id, task in reporting_service.active_tasks.items():
        status_message += (
            f"Task {task_id}:\n"
            f"- Status: {task['status']}\n"
            f"- Success: {task['success_count']}\n"
            f"- Failed: {task['failed_count']}\n"
            f"- Started: {task['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
    
    await update.message.reply_text(status_message)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop specific or all reporting tasks."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return

    if context.args:
        task_id = context.args[0]
        if await bot.reporting_service.stop_task(task_id):
            await update.message.reply_text(f"Task {task_id} stopped.")
        else:
            await update.message.reply_text(f"Task {task_id} not found.")
    else:
        async with bot.reporting_service.task_lock:
            for task_id in bot.reporting_service.active_tasks:
                bot.reporting_service.active_tasks[task_id]['status'] = 'stopped'
        await update.message.reply_text("All tasks stopped.")

async def sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show session status overview."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return

    session_count = len(bot.session_manager.get_active_sessions())
    await update.message.reply_text(f"Active Sessions: {session_count}")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retrieve recent operation logs."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return

    try:
        with open('bot.log', 'r') as f:
            logs = f.readlines()[-10:]  # Last 10 lines
        await update.message.reply_text("Recent logs:\n" + "".join(logs))
    except Exception as e:
        await update.message.reply_text(f"Error reading logs: {e}")

async def add_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate session addition process."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return ConversationHandler.END

    await update.message.reply_text("How many session strings do you want to add?")
    return ADD_SESSION_COUNT

async def add_session_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store number of sessions to add and prompt for input."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return ConversationHandler.END

    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("Please enter a positive number.")
            return ADD_SESSION_COUNT
        context.user_data['session_count'] = count
        context.user_data['sessions_added'] = []
        context.user_data['current_session'] = 1
        await update.message.reply_text(f"Please provide session string 1 of {count}")
        return ADD_SESSION_INPUT
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return ADD_SESSION_COUNT

async def add_session_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect session strings and save them."""
    bot = context.application.bot_data['bot']
    if not bot.is_authorized(update):
        await update.message.reply_text("Unauthorized access. Admin or premium users only.")
        return ConversationHandler.END

    session_string = update.message.text
    context.user_data['sessions_added'].append(session_string)

    current = context.user_data['current_session']
    total = context.user_data['session_count']

    client = TelegramClient(session_string, bot.config['api_id'], bot.config['api_hash'])
    if await bot.session_manager.validate_session(client):
        bot.session_manager.active_clients.append(client)
        bot.session_manager.save_sessions()
        logger.info(f"Added session {current} successfully")
    else:
        await update.message.reply_text(f"Invalid session string {current}. It will be skipped.")

    if current < total:
        context.user_data['current_session'] += 1
        await update.message.reply_text(f"Please provide session string {current + 1} of {total}")
        return ADD_SESSION_INPUT
    else:
        await update.message.reply_text(f"Added {len(context.user_data['sessions_added'])} sessions successfully!")
        context.user_data.clear()
        return ConversationHandler.END

async def add_premium_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate premium user addition process."""
    bot = context.application.bot_data['bot']
    if not bot.is_admin(update):
        await update.message.reply_text("Unauthorized access. Admin only.")
        return ConversationHandler.END

    await update.message.reply_text("Please provide a user ID or username (@username) to add as a premium user.")
    return ADD_PREMIUM
