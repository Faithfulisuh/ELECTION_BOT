from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from datetime import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging
import threading
import http.server
import socketserver
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_EMAIL = 1
WAITING_FOR_VERIFICATION = 2
VOTING_PRESIDENT = 3
VOTING_VICE_PRESIDENT = 4
VOTING_ASSISTANT_SECRETARY = 5
VOTING_PRO = 6
VOTING_DO_SOCIALS = 7
VOTING_DO_SPORTS = 8

authenticated_users = set()
user_votes = {}

def setup_google_sheets():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        expected_headers = [
            "Chat ID", "Email", "Name", "TtED_President", "Vice_President",
            "Rachel_Assistant_Secretary", "Lionel_PRO", "Marvellous_DO_Socials",
            "AbleGod_DO_Sports", "Timestamp"
        ]
        current_headers = sheet.row_values(1)
        if not current_headers or current_headers != expected_headers:
            sheet.clear()
            sheet.append_row(expected_headers)
        return sheet
    except Exception as e:
        logger.error(f"Failed to setup Google Sheets: {e}")
        return None

def load_voter_data():
    try:
        with open('voter_emails.json', 'r') as f:
            emails = json.load(f)
        with open('voter_names.json', 'r') as f:
            names = json.load(f)
        with open('verification_codes.json', 'r') as f:
            codes = json.load(f)
        return emails, names, codes
    except Exception as e:
        logger.error(f"Failed to load voter data: {e}")
        return [], [], []

def verify_voter(email, name, code):
    emails, names, codes = load_voter_data()
    if email in emails:
        return True
    return False

def store_vote(sheet, chat_id, email, name, votes):
    try:
        timestamp = datetime.now().isoformat()
        row_data = [
            str(chat_id), email, name,
            votes.get('president', ''), votes.get('vice_president', ''),
            votes.get('assistant_secretary', ''), votes.get('pro', ''),
            votes.get('do_socials', ''), votes.get('do_sports', ''), timestamp
        ]
        sheet.append_row(row_data)
        return True
    except Exception as e:
        logger.error(f"Failed to store vote: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in authenticated_users:
        await update.message.reply_text("You have already voted in this session. Thank you!")
        return ConversationHandler.END
    await update.message.reply_text("Welcome to the NADEESTU Voting Bot. Please enter your registered email:")
    return WAITING_FOR_EMAIL

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip().lower()
    if '@' not in email or '.' not in email:
        await update.message.reply_text("❌ Invalid email. Try again:")
        return WAITING_FOR_EMAIL
    context.user_data['email'] = email
    await update.message.reply_text("Enter your full name:")
    return WAITING_FOR_VERIFICATION

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'verification_step' not in context.user_data:
        context.user_data['name'] = update.message.text.strip()
        context.user_data['verification_step'] = 'code'
        await update.message.reply_text("Enter your verification code:")
        return WAITING_FOR_VERIFICATION
    else:
        code = update.message.text.strip()
        email = context.user_data['email']
        name = context.user_data['name']
        if verify_voter(email, name, code):
            user_id = update.effective_user.id
            authenticated_users.add(user_id)
            user_votes[user_id] = {}
            context.user_data['sheet'] = setup_google_sheets()
            if not context.user_data['sheet']:
                await update.message.reply_text("❌ Could not connect to Google Sheets.")
                return ConversationHandler.END
            await update.message.reply_text("TtED for President: Vote Yes or No")
            return VOTING_PRESIDENT
        else:
            await update.message.reply_text("❌ Invalid verification. Try code again:")
            return WAITING_FOR_VERIFICATION

async def handle_president_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip().lower()
    if vote not in ['yes', 'no']:
        await update.message.reply_text("Vote Yes or No only:")
        return VOTING_PRESIDENT
    user_id = update.effective_user.id
    user_votes[user_id]['president'] = vote.capitalize()
    keyboard = [[KeyboardButton("Wizzywise"), KeyboardButton("BennieBliss")]]
    await update.message.reply_text("Vice President: Choose one:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return VOTING_VICE_PRESIDENT

async def handle_vice_president_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip()
    if vote not in ['Wizzywise', 'BennieBliss']:
        await update.message.reply_text("❌ Invalid choice. Choose Wizzywise or BennieBliss:")
        return VOTING_VICE_PRESIDENT
    user_id = update.effective_user.id
    user_votes[user_id]['vice_president'] = vote
    await update.message.reply_text("Rachel for Assistant Secretary: Vote Yes or No", reply_markup=ReplyKeyboardRemove())
    return VOTING_ASSISTANT_SECRETARY

async def handle_assistant_secretary_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip().lower()
    if vote not in ['yes', 'no']:
        await update.message.reply_text("Vote Yes or No only:")
        return VOTING_ASSISTANT_SECRETARY
    user_id = update.effective_user.id
    user_votes[user_id]['assistant_secretary'] = vote.capitalize()
    await update.message.reply_text("Lionel for PRO: Vote Yes or No")
    return VOTING_PRO

async def handle_pro_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip().lower()
    if vote not in ['yes', 'no']:
        await update.message.reply_text("Vote Yes or No only:")
        return VOTING_PRO
    user_id = update.effective_user.id
    user_votes[user_id]['pro'] = vote.capitalize()
    await update.message.reply_text("Marvellous for DO Socials: Vote Yes or No")
    return VOTING_DO_SOCIALS

async def handle_do_socials_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip().lower()
    if vote not in ['yes', 'no']:
        await update.message.reply_text("Vote Yes or No only:")
        return VOTING_DO_SOCIALS
    user_id = update.effective_user.id
    user_votes[user_id]['do_socials'] = vote.capitalize()
    await update.message.reply_text("AbleGod for DO Sports: Vote Yes or No")
    return VOTING_DO_SPORTS

async def handle_do_sports_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vote = update.message.text.strip().lower()
    if vote not in ['yes', 'no']:
        await update.message.reply_text("Vote Yes or No only:")
        return VOTING_DO_SPORTS
    user_id = update.effective_user.id
    user_votes[user_id]['do_sports'] = vote.capitalize()
    sheet = context.user_data.get('sheet')
    if sheet:
        store_vote(sheet, update.effective_user.id, context.user_data['email'], context.user_data['name'], user_votes[user_id])
        await update.message.reply_text("✅ Voting complete. Thank you for participating!")
    else:
        await update.message.reply_text("❌ Could not save vote. Contact admin.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Voting cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗳️ Use /start to begin voting or /cancel to stop.")

def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        logger.info(f"🌐 Dummy HTTP server running on port {PORT}.")
        httpd.serve_forever()

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FOR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            WAITING_FOR_VERIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_verification)],
            VOTING_PRESIDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_president_vote)],
            VOTING_VICE_PRESIDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vice_president_vote)],
            VOTING_ASSISTANT_SECRETARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_assistant_secretary_vote)],
            VOTING_PRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pro_vote)],
            VOTING_DO_SOCIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_do_socials_vote)],
            VOTING_DO_SPORTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_do_sports_vote)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    server_thread = threading.Thread(target=run_dummy_server)
    server_thread.start()

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
