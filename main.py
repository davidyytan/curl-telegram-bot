import os
import json
import time
import logging
import asyncio
import requests
import re
import random
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TARGET_URL = os.getenv('TARGET_URL')
KEYWORDS_CASE_INSENSITIVE = [k.strip() for k in os.getenv('KEYWORDS_CASE_INSENSITIVE', '').split(',') if k.strip()]
KEYWORDS_CASE_SENSITIVE = [k.strip() for k in os.getenv('KEYWORDS_CASE_SENSITIVE', '').split(',') if k.strip()]
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))  # Default: 5 minutes

# Validate required environment variables
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required")
if not TARGET_URL:
    raise ValueError("TARGET_URL environment variable is required")
if not CHAT_ID:
    logger.warning("CHAT_ID environment variable is not set. Notifications will not be sent automatically.")

# Monitoring control
monitoring_active = False
monitoring_task = None

# Rate limiting
last_api_call_time = 0
MIN_API_CALL_INTERVAL = 1  # Minimum 1 second between API calls


def fetch_json_data(url):
    """Fetch JSON data from the specified URL with rate limiting."""
    global last_api_call_time
    
    # Apply rate limiting
    current_time = time.time()
    time_since_last_call = current_time - last_api_call_time
    
    if time_since_last_call < MIN_API_CALL_INTERVAL:
        sleep_time = MIN_API_CALL_INTERVAL - time_since_last_call
        logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)
    
    last_api_call_time = time.time()
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Validate that the response is valid JSON
        try:
            return response.json()
        except ValueError as json_err:
            logger.error(f"Invalid JSON response: {json_err}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {e}")
        return None


def check_for_keywords(data):
    """Check if any keywords are present in the JSON data."""
    found_keywords = {
        'case_insensitive': [],
        'case_sensitive': []
    }
    
    def search_in_data(obj, keyword, case_sensitive=False):
        """Recursively search for keyword in data structure."""
        if isinstance(obj, dict):
            # Search in keys and values
            for key, value in obj.items():
                if search_whole_word(str(key), keyword, case_sensitive) or search_in_data(value, keyword, case_sensitive):
                    return True
        elif isinstance(obj, list):
            # Search in list items
            for item in obj:
                if search_in_data(item, keyword, case_sensitive):
                    return True
        elif isinstance(obj, str):
            # Direct string search (whole word only)
            return search_whole_word(obj, keyword, case_sensitive)
        else:
            # For other types (int, float, bool, None), convert to string
            return search_whole_word(str(obj), keyword, case_sensitive)
        return False
    
    def search_whole_word(text, keyword, case_sensitive=False):
        """Search for whole word matches using regex word boundaries."""
        # Escape special regex characters in the keyword
        escaped_keyword = re.escape(keyword)
        # Use word boundaries to match whole words only
        pattern = r'\b' + escaped_keyword + r'\b'
        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.search(pattern, text, flags))
    
    # Check case-insensitive keywords
    for keyword in KEYWORDS_CASE_INSENSITIVE:
        if keyword.strip() and search_in_data(data, keyword, case_sensitive=False):
            found_keywords['case_insensitive'].append(keyword)
    
    # Check case-sensitive keywords
    for keyword in KEYWORDS_CASE_SENSITIVE:
        if keyword.strip() and search_in_data(data, keyword, case_sensitive=True):
            found_keywords['case_sensitive'].append(keyword)
    
    # Return flattened list of all found keywords for backward compatibility
    all_found = found_keywords['case_insensitive'] + found_keywords['case_sensitive']
    return all_found, found_keywords


def has_data_changed(data):
    """Check if the data has changed since the last check."""
    global last_data_hash
    
    # Calculate a hash of the data for comparison
    current_hash = hash(json.dumps(data, sort_keys=True))
    
    if last_data_hash is None:
        last_data_hash = current_hash
        return False
    
    has_changed = current_hash != last_data_hash
    last_data_hash = current_hash
    return has_changed


def format_data(data):
    return "Edit this to query response from your url."


async def send_notification(chat_id, message):
    """Send a notification message to a chat."""
    try:
        async with Bot(token=TELEGRAM_TOKEN) as bot:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            logger.info("Message sent successfully")
            return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


async def check_and_notify(context: ContextTypes.DEFAULT_TYPE):
    """Main function to check the URL and notify if needed."""
    chat_id = CHAT_ID
    data = fetch_json_data(TARGET_URL)
    
    if data is None:
        logger.warning("Failed to fetch data, skipping this check")
        return
    
    data_changed = has_data_changed(data)
    found_keywords, keyword_details = check_for_keywords(data)
    
    # Prepare notification if needed
    if data_changed or found_keywords:
        message_parts = []
        
        if data_changed:
            message_parts.append("🔄 *Data has been updated!*")
        
        if found_keywords:
            keyword_msg = "🔎 *Found keywords:*\n"
            if keyword_details['case_insensitive']:
                keyword_msg += f"• Case-insensitive: {', '.join(keyword_details['case_insensitive'])}\n"
            if keyword_details['case_sensitive']:
                keyword_msg += f"• Case-sensitive: {', '.join(keyword_details['case_sensitive'])}"
            message_parts.append(keyword_msg)
        
        message = "\n\n".join(message_parts)
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

        # Send formatted data
        data_message = format_data(data)
        await context.bot.send_message(chat_id=chat_id, text=data_message, parse_mode='Markdown')


async def fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /fetch command to manually fetch and return data once."""
    await update.message.reply_text("🔄 *Fetching data once...*", parse_mode='Markdown')
    
    # One-time data fetch
    data = fetch_json_data(TARGET_URL)
    
    if data is None:
        await update.message.reply_text("❌ *Error: Failed to fetch data*", parse_mode='Markdown')
        return
    
    # Check for keywords and notify about them
    found_keywords, keyword_details = check_for_keywords(data)
    
    if found_keywords:
        keyword_msg = "🔎 *Keywords found:*\n"
        if keyword_details['case_insensitive']:
            keyword_msg += f"• Case-insensitive: {', '.join(keyword_details['case_insensitive'])}\n"
        if keyword_details['case_sensitive']:
            keyword_msg += f"• Case-sensitive: {', '.join(keyword_details['case_sensitive'])}"
    else:
        keyword_msg = "❌ *No keywords found*"
    
    await update.message.reply_text(keyword_msg, parse_mode='Markdown')
    
    # Always send the data regardless of keywords
    data_message = format_data(data)
    await update.message.reply_text(data_message, parse_mode='Markdown')


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command to start monitoring."""
    global monitoring_active, monitoring_task
    
    if monitoring_active:
        await update.message.reply_text("⚠️ *Monitoring is already active*", parse_mode='Markdown')
        return
    
    # Initialize last_data_hash if not already set
    global last_data_hash
    if last_data_hash is None:
        data = fetch_json_data(TARGET_URL)
        if data:
            last_data_hash = hash(json.dumps(data, sort_keys=True))
    
    monitoring_active = True
    job_queue = context.application.job_queue
    randomized_interval = CHECK_INTERVAL * random.uniform(0.9, 1.1)
    monitoring_task = job_queue.run_repeating(check_and_notify, interval=randomized_interval, first=1)
    
    # Format keywords for display
    all_keywords = []
    if KEYWORDS_CASE_INSENSITIVE:
        all_keywords.append(f"Case-insensitive: {', '.join(KEYWORDS_CASE_INSENSITIVE)}")
    if KEYWORDS_CASE_SENSITIVE:
        all_keywords.append(f"Case-sensitive: {', '.join(KEYWORDS_CASE_SENSITIVE)}")
    
    keywords_display = '\n'.join(all_keywords) if all_keywords else 'No keywords set'
    
    status_message = (
        "✅ *Monitoring started!*\n\n"
        f"Checking URL every {CHECK_INTERVAL} seconds for keywords:\n"
        f"{keywords_display}"
    )
    await update.message.reply_text(status_message, parse_mode='Markdown')


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /stop command to stop monitoring."""
    global monitoring_active, monitoring_task
    
    if not monitoring_active:
        await update.message.reply_text("⚠️ *Monitoring is not active*", parse_mode='Markdown')
        return
    
    monitoring_active = False
    
    # Remove the specific job instead of stopping/starting the queue
    if monitoring_task:
        monitoring_task.schedule_removal()
        monitoring_task = None
    
    await update.message.reply_text("🛑 *Monitoring stopped*", parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command to show available commands."""
    # Format keywords for display
    all_keywords = []
    if KEYWORDS_CASE_INSENSITIVE:
        all_keywords.append(f"Case-insensitive: {', '.join(KEYWORDS_CASE_INSENSITIVE)}")
    if KEYWORDS_CASE_SENSITIVE:
        all_keywords.append(f"Case-sensitive: {', '.join(KEYWORDS_CASE_SENSITIVE)}")
    
    keywords_display = '\n'.join(all_keywords) if all_keywords else 'No keywords set'
    
    help_text = (
        "🤖 *Monitoring Bot Commands*\n\n"
        "/start - Start monitoring the target URL\n"
        "/stop - Stop monitoring the target URL\n"
        "/fetch - Fetch data now and check for keywords\n"
        "/help - Show this help message\n\n"
        f"Currently monitoring for keywords:\n{keywords_display}"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def post_init(application: Application):
    """Code to run after initialization but before polling starts."""
    # Send a notification that the bot is online
    if CHAT_ID:
        await send_notification(CHAT_ID, "🤖 *Bot is online!*\nUse /help to see available commands.")


def main():
    """Set up the bot with command handlers and start the application."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fetch", fetch_command))
    
    # Initialize last_data_hash variable
    global last_data_hash
    last_data_hash = None
    
    # Set up post-initialization code
    application.post_init = post_init
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
