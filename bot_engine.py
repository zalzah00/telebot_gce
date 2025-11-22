import os
import sys
import logging
import datetime
import psutil # NEW: For system metrics
import requests # NEW: For potential future HTTP checks

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

# --- Setup and Initialization ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Constants
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
TELEGRAM_MAX_MESSAGE_LENGTH = 4096 

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.error("TELEGRAM_TOKEN or GEMINI_API_KEY environment variable not set.")
    sys.exit(1)

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client: {e}")
    sys.exit(1)


# --- NEW Helper Function for Status Check ---

def get_health_status():
    """Gathers basic system health statistics."""
    try:
        # psutil.cpu_percent(interval=None) makes the check non-blocking
        cpu_usage = psutil.cpu_percent(interval=None) 
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status_message = (
            f"🤖 **Bot Health Status Report**\n"
            f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"🖥️ **VM System Stats:**\n"
            f"  - **CPU Usage:** `{cpu_usage:.1f}%`\n"
            f"  - **RAM Used:** `{mem.percent:.1f}%` ({mem.used / (1024**3):.2f} GB)\n"
            f"  - **Disk Used:** `{disk.percent:.1f}%` ({disk.used / (1024**3):.2f} GB)\n"
            f"\n"
            f"💡 **Service Status:** Running persistently inside Tmux/Screen\n"
        )
        return status_message
    except Exception as e:
        return f"🚨 **Health Check Failed:** Could not gather system metrics. Error: {e}"


# --- Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    logger.info(f"User {update.effective_user.id} used /start command.")
    await update.message.reply_text(
        "👋 Hello! I'm a bot powered by Google's Gemini AI.\n"
        "Just send me a message and I'll do my best to respond!\n"
        "Use /help to see available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message."""
    logger.info(f"User {update.effective_user.id} used /help command.")
    await update.message.reply_text(
        "📝 **Available Commands:**\n"
        "/start - Start the conversation\n"
        "/help - Show this help message\n"
        "/status - Get the VM system health report\n\n"
        "To chat, just send a text message directly."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs the health check and displays the status report."""
    logger.info(f"User {update.effective_user.id} used /status command.")
    
    # 1. Generate the status report
    status_report = get_health_status()
    
    # 2. Reply with the report
    await update.message.reply_text(status_report, parse_mode='Markdown')


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages and calls the Gemini API."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    logger.info(f"Received message from chat {chat_id}: '{user_message[:50]}...'")

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_message,
        )

        gemini_response_text = response.text.strip()
        
        # Split and send long messages
        if len(gemini_response_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            messages = [
                gemini_response_text[i:i + TELEGRAM_MAX_MESSAGE_LENGTH]
                for i in range(0, len(gemini_response_text), TELEGRAM_MAX_MESSAGE_LENGTH)
            ]
        else:
            messages = [gemini_response_text]

        for message in messages:
            await update.message.reply_text(message)

        logger.info(f"Replied to chat {chat_id} with Gemini text (Sent {len(messages)} chunk(s)).")

    except APIError as e:
        logger.error(f"Gemini API Error for chat {chat_id}: {e}")
        await update.message.reply_text(
            "An error occurred while communicating with the Gemini API. Please try again later."
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred for chat {chat_id}: {e}")
        await update.message.reply_text(
            "An unexpected error occurred. Please check the bot logs."
        )


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command)) # <-- NEW HANDLER REGISTERED
    
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler)
    )

    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()