import os
import json
import time
import logging
import asyncio
import requests
from telegram import Bot
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
KEYWORDS = os.getenv('KEYWORDS', '').split(',')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))  # Default: 5 minutes

# Initialize the bot
bot = Bot(token=TELEGRAM_TOKEN)

# Store the last fetched data to detect updates
last_data_hash = None


def fetch_json_data(url):
    """Fetch JSON data from the specified URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {e}")
        return None


def check_for_keywords(data, keywords):
    """Check if any keywords are present in the JSON data."""
    # Convert JSON to string for simple keyword searching
    data_str = json.dumps(data).lower()
    found_keywords = []
    
    for keyword in keywords:
        if keyword.lower() in data_str:
            found_keywords.append(keyword)
    
    return found_keywords


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


async def send_telegram_message(message):
    """Send a message to the specified Telegram chat."""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        logger.info("Message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


async def check_and_notify():
    """Main function to check the URL and notify if needed."""
    data = fetch_json_data(TARGET_URL)
    
    if data is None:
        logger.warning("Failed to fetch data, skipping this check")
        return
    
    data_changed = has_data_changed(data)
    found_keywords = check_for_keywords(data, KEYWORDS)
    
    # Prepare notification if needed
    if data_changed or found_keywords:
        message_parts = []
        
        if data_changed:
            message_parts.append("🔄 *Data has been updated!*")
        
        if found_keywords:
            message_parts.append(f"🔎 *Found keywords:* {', '.join(found_keywords)}")
        
        message = "\n\n".join(message_parts)
        await send_telegram_message(message)

async def main():
    """Run the bot in a loop, checking periodically."""
    logger.info(f"Bot started. Checking {TARGET_URL} every {CHECK_INTERVAL} seconds for keywords: {KEYWORDS}")
    
    # Send initial message to confirm the bot is running
    await send_telegram_message("🤖 *Monitoring bot started!*\nI'll notify you of any updates or keywords.")
    
    try:
        while True:
            await check_and_notify()
            await asyncio.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await send_telegram_message(f"⚠️ *Bot error:* {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
