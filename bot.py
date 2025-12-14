import os
import json
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import aiohttp
from collections import defaultdict

# Configuration
TOKEN = "7216255079:AAESgFa8k5WbxYxrHLFxlSMcZ05AH0Q6BaE"
API_URL = "http://206.189.214.238:8080/search"
ADMIN_IDS = [8005797405]
GROUP_IDS = []

# Rate limiting
RATE_LIMIT = timedelta(seconds=60)
user_last_request = defaultdict(datetime)

class OSINTBot:
    def __init__(self):
        self.session = None
        
    async def init_session(self):
        self.session = aiohttp.ClientSession()
        
    async def search_api(self, query: str, is_url: bool = False) -> Optional[Dict]:
        try:
            params = {'url': query} if is_url else {'keyword': query}
            
            async with self.session.get(API_URL, params=params, timeout=30) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"API Error: {e}")
            return None
            
    def format_result(self, data: List[Dict], limit: int = None) -> str:
        if not data:
            return "No results found."
            
        if limit:
            data = data[:limit]
            
        lines = []
        for i, item in enumerate(data, 1):
            lines.append(f"Result {i}:")
            lines.append(f"  URL: {item.get('URL', 'N/A')}")
            lines.append(f"  Username: {item.get('Username', 'N/A')}")
            lines.append(f"  Password: {item.get('Password', 'N/A')}")
            lines.append("")
            
        return "\n".join(lines)
        
    def create_file_content(self, data: List[Dict], limit: int = None) -> str:
        if limit:
            data = data[:limit]
            
        content = []
        for item in data:
            content.append(f"URL: {item.get('URL', 'N/A')}")
            content.append(f"Username: {item.get('Username', 'N/A')}")
            content.append(f"Password: {item.get('Password', 'N/A')}")
            content.append("-" * 40)
            
        return "\n".join(content)
        
    def check_rate_limit(self, user_id: int) -> bool:
        now = datetime.now()
        last_request = user_last_request.get(user_id)
        
        if last_request and now - last_request < RATE_LIMIT:
            wait_time = RATE_LIMIT - (now - last_request)
            return False, wait_time.seconds
            
        user_last_request[user_id] = now
        return True, 0
        
    def is_valid_group(self, chat_id: int) -> bool:
        if not GROUP_IDS:
            return True
        return chat_id in GROUP_IDS

bot = OSINTBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    if update.effective_chat.type == "private":
        welcome_text = (
            "OSINT Bot\n\n"
            "Commands:\n"
            "/free <keyword or url> - Get 12 results (group only)\n"
            "/paid <keyword or url> - Get all results (private)\n\n"
            "For paid services, contact admin."
        )
        
        if is_admin:
            welcome_text += "\n\nAdmin access granted."
            
        await update.message.reply_text(welcome_text)
    else:
        await update.message.reply_text(
            "OSINT Bot is active in this group.\n"
            "Use /free <keyword or url> to search."
        )

async def free_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not bot.is_valid_group(chat_id):
        await update.message.reply_text("This command only works in authorized groups.")
        return
        
    if not context.args:
        await update.message.reply_text("Please provide a keyword or URL.\nExample: /free wehostbd.com")
        return
        
    query = " ".join(context.args)
    
    allowed, wait_time = bot.check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"Rate limit exceeded. Please wait {wait_time} seconds.")
        return
        
    processing_msg = await update.message.reply_text("Processing free search...")
    
    is_url = query.startswith(('http://', 'https://'))
    result = await bot.search_api(query, is_url)
    
    if not result or result.get('status') != 'success':
        await processing_msg.edit_text("Search failed or no results found.")
        return
        
    data = result.get('data', [])
    
    if not data:
        await processing_msg.edit_text("No results found for your query.")
        return
        
    display_text = bot.format_result(data, limit=12)
    
    if len(data) > 12:
        display_text += f"\nShowing 12 out of {len(data)} results. Use /paid for full results."
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"free_results_{timestamp}.txt"
    
    file_content = bot.create_file_content(data, limit=12)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    caption = (
        f"Free Search Results\n"
        f"Query: {query}\n"
        f"Total results found: {len(data)}\n"
        f"Results in file: {min(12, len(data))}\n"
        f"Time taken: {result.get('time_taken_seconds', 0):.2f}s"
    )
    
    with open(filename, 'rb') as f:
        await update.message.reply_document(
            document=f,
            filename=filename,
            caption=caption,
            reply_to_message_id=update.message.message_id
        )
    
    os.remove(filename)
    await processing_msg.delete()

async def paid_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if chat_id not in ADMIN_IDS and chat_id > 0:
        await update.message.reply_text(
            "Paid search is only available for admins.\n"
            "Contact admin for access."
        )
        return
        
    if not context.args:
        await update.message.reply_text("Please provide a keyword or URL.\nExample: /paid wehostbd.com")
        return
        
    query = " ".join(context.args)
    
    allowed, wait_time = bot.check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"Rate limit exceeded. Please wait {wait_time} seconds.")
        return
        
    processing_msg = await update.message.reply_text("Processing paid search...")
    
    is_url = query.startswith(('http://', 'https://'))
    result = await bot.search_api(query, is_url)
    
    if not result or result.get('status') != 'success':
        await processing_msg.edit_text("Search failed or no results found.")
        return
        
    data = result.get('data', [])
    
    if not data:
        await processing_msg.edit_text("No results found for your query.")
        return
        
    download_link = result.get('download', '')
    if download_link:
        download_url = f"http://206.189.214.238:8080{download_link}"
        await update.message.reply_text(
            f"Full dataset available at:\n{download_url}\n\n"
            f"Results found: {len(data)}\n"
            f"Time taken: {result.get('time_taken_seconds', 0):.2f}s\n"
            f"Session: {result.get('used_session', 'N/A')}"
        )
    else:
        display_text = bot.format_result(data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"paid_results_{timestamp}.txt"
        
        file_content = bot.create_file_content(data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        caption = (
            f"Paid Search Results\n"
            f"Query: {query}\n"
            f"Total results: {len(data)}\n"
            f"Time taken: {result.get('time_taken_seconds', 0):.2f}s"
        )
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=caption,
                reply_to_message_id=update.message.message_id
            )
        
        os.remove(filename)
    
    await processing_msg.delete()

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Admin only command.")
        return
        
    if not context.args:
        await update.message.reply_text("Please provide group ID.\nExample: /addgroup -1001234567890")
        return
        
    try:
        group_id = int(context.args[0])
        if group_id not in GROUP_IDS:
            GROUP_IDS.append(group_id)
            await update.message.reply_text(f"Group {group_id} added successfully.")
        else:
            await update.message.reply_text("Group already added.")
    except ValueError:
        await update.message.reply_text("Invalid group ID.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Admin only command.")
        return
        
    stats_text = (
        f"Bot Statistics\n"
        f"Total groups: {len(GROUP_IDS)}\n"
        f"Active sessions: {len(user_last_request)}\n"
        f"Rate limit: 1 request per minute"
    )
    
    await update.message.reply_text(stats_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("An error occurred. Please try again.")
        except:
            pass

async def main():
    await bot.init_session()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("free", free_search))
    app.add_handler(CommandHandler("paid", paid_search))
    app.add_handler(CommandHandler("addgroup", add_group))
    app.add_handler(CommandHandler("stats", stats))
    
    app.add_error_handler(error_handler)
    
    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
