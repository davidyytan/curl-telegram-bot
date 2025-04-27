# Telegram Monitoring Bot

A Python bot that monitors a JSON endpoint and sends Telegram notifications when:
- Data changes are detected
- Specified keywords appear in the data

## Features

- Periodic checking of a JSON API endpoint
- Change detection using hash comparison
- Keyword monitoring in JSON data
- Telegram notifications with formatting

## Requirements

- Python 3.7+
- A Telegram bot token (from [@BotFather](https://t.me/botfather))
- A Telegram chat ID

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your configuration (see below)

## Configuration

Create a `.env` file in the project root with the following variables:

```
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TARGET_URL=https://api.example.com/data.json
KEYWORDS=keyword1,keyword2,important_term
CHECK_INTERVAL=300
```

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Your Telegram bot API token |
| `TELEGRAM_CHAT_ID` | The chat ID where notifications will be sent |
| `TARGET_URL` | The URL of the JSON endpoint to monitor |
| `KEYWORDS` | Comma-separated list of keywords to look for |
| `CHECK_INTERVAL` | Time between checks in seconds (default: 300) |

### Getting Telegram Token and Chat ID

1. **Creating a bot and getting a token**:
   - Start a chat with [@BotFather](https://t.me/botfather) on Telegram
   - Send the command `/newbot` and follow the instructions
   - Once created, BotFather will provide you with a token (like `123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ`)

2. **Getting your Chat ID**:
   - Method 1: Send a message to [@userinfobot](https://t.me/userinfobot)
   - Method 2: Send a message to your new bot, then access this URL:
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Look for the "chat" object which contains "id"

## Usage

Run the bot with:

```
python main.py
```

The bot will start monitoring the configured URL and send notifications to your Telegram chat when changes or specified keywords are detected.

> **Note**: If your API endpoint is geo-restricted, consider using a VPN before making requests to the endpoint.

## Notification Format

- 🔄 **Data has been updated!** - When the JSON data changes
- 🔎 **Found keywords:** keyword1, keyword2 - When specified keywords are found 