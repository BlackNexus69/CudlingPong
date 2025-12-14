# advanced_features.py
import asyncio
import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.create_tables()
        
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_admin BOOLEAN DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                search_type TEXT,
                results_count INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def log_search(self, user_id: int, query: str, search_type: str, results_count: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO searches (user_id, query, search_type, results_count)
            VALUES (?, ?, ?, ?)
        ''', (user_id, query, search_type, results_count))
        self.conn.commit()
    
    def get_user_stats(self, user_id: int) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as total_searches,
                   COUNT(CASE WHEN search_type = 'free' THEN 1 END) as free_searches,
                   COUNT(CASE WHEN search_type = 'paid' THEN 1 END) as paid_searches
            FROM searches
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        return {
            'total_searches': result[0] if result else 0,
            'free_searches': result[1] if result else 0,
            'paid_searches': result[2] if result else 0
        }

# Add to main bot class
class EnhancedOSINTBot(OSINTBot):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.blacklist = set()
        
    def check_blacklist(self, query: str) -> bool:
        """Check if query contains blacklisted terms"""
        blacklisted_terms = ['admin', 'password', 'login', 'wp-login']
        return any(term in query.lower() for term in blacklisted_terms)
        
    async def validate_query(self, query: str) -> tuple:
        """Validate search query"""
        if len(query) < 3:
            return False, "Query too short (minimum 3 characters)"
            
        if len(query) > 100:
            return False, "Query too long (maximum 100 characters)"
            
        if self.check_blacklist(query):
            return False, "Query contains restricted terms"
            
        return True, "Valid"

# Add new command handlers
async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = bot.db.get_user_stats(user_id)
    
    stats_text = (
        f"Your Statistics\n"
        f"Total searches: {stats['total_searches']}\n"
        f"Free searches: {stats['free_searches']}\n"
        f"Paid searches: {stats['paid_searches']}"
    )
    
    await update.message.reply_text(stats_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "OSINT Bot Help\n\n"
        "Available Commands:\n"
        "/free <query> - Free search (12 results max)\n"
        "/paid <query> - Paid search (full results)\n"
        "/mystats - Your search statistics\n"
        "/help - This help message\n\n"
        "Query Examples:\n"
        "/free wehostbd.com\n"
        "/free target.com login\n"
        "/paid https://example.com\n\n"
        "Note: 1 request per minute limit applies."
    )
    
    await update.message.reply_text(help_text)

# Update main function to include new handlers
async def enhanced_main():
    global bot
    bot = EnhancedOSINTBot()
    await bot.init_session()
    
    app = Application.builder().token(TOKEN).build()
    
    # Add all handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("free", free_search))
    app.add_handler(CommandHandler("paid", paid_search))
    app.add_handler(CommandHandler("addgroup", add_group))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("mystats", my_stats))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_error_handler(error_handler)
    
    print("Enhanced bot is running...")
    await app.run_polling()

# Add this to requirements.txt
"""
python-telegram-bot==20.7
aiohttp==3.9.0
requests==2.31.0
