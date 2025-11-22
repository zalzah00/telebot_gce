import os
import logging
from dotenv import load_dotenv

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

# --- Setup and Initialization ---

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Constants
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"  # Specify the model
TELEGRAM_MAX_MESSAGE_LENGTH = 4096 # Max characters Telegram allows in one message

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.error("TELEGRAM_TOKEN or GEMINI_API_KEY environment variable not set.")
    exit(1)

# Initialize the Google Gemini Client
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client: {e}")
    exit(1)


# --- Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} used /start command.")
    await update.message.reply_text(
        "👋 Hello! I'm a bot powered by Google's Gemini AI.\n"
        "Just send me a message and I'll do my best to respond!\n"
        "Use /help to see available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the command /help is issued."""
    logger.info(f"User {update.effective_user.id} used /help command.")
    await update.message.reply_text(
        "📝 **Available Commands:**\n"
        "/start - Start the conversation\n"
        "/help - Show this help message\n\n"
        "To chat, just send a text message directly."
    )


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles text messages, calls the Gemini API, and replies,
    splitting the response if it exceeds Telegram's message limit.
    """
    user_message = update.message.text
    chat_id = update.effective_chat.id
    logger.info(f"Received message from chat {chat_id}: '{user_message[:50]}...'")

    try:
        # Show 'typing...' status
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Call the Gemini API
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_message,
        )

        gemini_response_text = response.text.strip()
        
        # Check and split long messages to avoid Telegram's 4096 character limit
        if len(gemini_response_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            # Split the text into chunks
            messages = [
                gemini_response_text[i:i + TELEGRAM_MAX_MESSAGE_LENGTH]
                for i in range(0, len(gemini_response_text), TELEGRAM_MAX_MESSAGE_LENGTH)
            ]
        else:
            messages = [gemini_response_text]

        # Send all chunks as separate replies
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
    # Create the Application and pass your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Register the message handler for all text messages (that are not commands)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler)
    )

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()