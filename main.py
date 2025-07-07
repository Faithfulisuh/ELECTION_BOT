from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from datetime import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging
# from config import TELEGRAM_BOT_TOKEN, SPREADSHEET_ID

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access the variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
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

# Global variables
MAX_RETRIES = 3
authenticated_users = set()
user_votes = {}

# Google Sheets setup
def setup_google_sheets():
    """Initialize Google Sheets connection."""
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Initialize headers if needed
        expected_headers = ["Chat ID", "Email", "Name", "TtED_President", "Vice_President", 
                           "Rachel_Assistant_Secretary", "Lionel_PRO", "Marvellous_DO_Socials", 
                           "AbleGod_DO_Sports", "Timestamp"]
        
        try:
            current_headers = sheet.row_values(1)
            if not current_headers:
                sheet.append_row(expected_headers)
        except:
            sheet.append_row(expected_headers)
            
        return sheet
    except Exception as e:
        logger.error(f"Failed to setup Google Sheets: {e}")
        return None

# Load voter data from JSON files
def load_voter_data():
    """Load voter emails, names, and verification codes from JSON files."""
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
    """Verify if voter credentials are valid."""
    emails, names, codes = load_voter_data()
    
    # Check if email exists and corresponds to the name and code
    if email in emails:
        # email_index = emails.index(email)
        # if (email_index < len(names) and email_index < len(codes) and
            # names[email_index].lower() == name.lower() and
            # codes[email_index] == code):
        return True
    return False
    # if email in emails:
        # email_index = emails.index(email)
        # if (email_index < len(names) and email_index < len(codes) and
            # names[email_index].lower() == name.lower() and
            # codes[email_index] == code):
            # return True
    # return False

def store_vote(sheet, chat_id, email, name, votes):
    """Store vote in Google Sheets."""
    try:
        timestamp = datetime.now().isoformat()
        row_data = [
            str(chat_id),
            email,
            name,
            votes.get('president', ''),
            votes.get('vice_president', ''),
            votes.get('assistant_secretary', ''),
            votes.get('pro', ''),
            votes.get('do_socials', ''),
            votes.get('do_sports', ''),
            timestamp
        ]
        sheet.append_row(row_data)
        return True
    except Exception as e:
        logger.error(f"Failed to store vote: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the voting process."""
    user_id = update.effective_user.id
    
    if user_id in authenticated_users:
        await update.message.reply_text(
            "You have already voted! Thank you for participating in the election."
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🗳️ Welcome to the Election Voting Platform!\n\n"
        "To participate in the election, you need to authenticate yourself.\n"
        "Please enter your registered email address:"
    )
    return WAITING_FOR_EMAIL

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input."""
    email = update.message.text.strip().lower()
    
    # Basic email validation
    if '@' not in email or '.' not in email:
        await update.message.reply_text(
            "❌ Please enter a valid email address:"
        )
        return WAITING_FOR_EMAIL
    
    context.user_data['email'] = email
    await update.message.reply_text(
        "📧 Email received. Now please enter your full name as registered:"
    )
    return WAITING_FOR_VERIFICATION

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name and verification."""
    if 'verification_step' not in context.user_data:
        # First step: get name
        context.user_data['name'] = update.message.text.strip()
        context.user_data['verification_step'] = 'code'
        await update.message.reply_text(
            "👤 Name received. Now please enter your verification code:"
        )
        return WAITING_FOR_VERIFICATION
    else:
        # Second step: get verification code
        code = update.message.text.strip()
        email = context.user_data['email']
        name = context.user_data['name']
        
        if verify_voter(email, name, code):
            user_id = update.effective_user.id
            authenticated_users.add(user_id)
            context.user_data['verified'] = True
            user_votes[user_id] = {}
            
            # Setup Google Sheets
            context.user_data['sheet'] = setup_google_sheets()
            if not context.user_data['sheet']:
                await update.message.reply_text(
                    "❌ System error. Please try again later."
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                "✅ Authentication successful! Let's begin voting.\n\n"
                "🏛️ **Question 1 of 6**\n"
                "**TtED for President**\n"
                "Please vote: Yes or No"
            )
            return VOTING_PRESIDENT
        else:
            await update.message.reply_text(
                "❌ Invalid credentials. Please check your information and try again.\n"
                "Enter your verification code:"
            )
            return WAITING_FOR_VERIFICATION

async def handle_president_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle president vote."""
    vote = update.message.text.strip().lower()
    
    if vote not in ['yes', 'no']:
        await update.message.reply_text(
            "❌ Please answer with 'Yes' or 'No' only.\n"
            "**TtED for President** - Your vote:"
        )
        return VOTING_PRESIDENT
    
    user_id = update.effective_user.id
    user_votes[user_id]['president'] = vote.capitalize()
    
    keyboard = [
        [KeyboardButton("Wizzywise"), KeyboardButton("BennieBliss")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "✅ Vote recorded!\n\n"
        "🏛️ **Question 2 of 6**\n"
        "**Vice President**\n"
        "Please choose one:",
        reply_markup=reply_markup
    )
    return VOTING_VICE_PRESIDENT

async def handle_vice_president_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle vice president vote."""
    vote = update.message.text.strip()
    
    if vote not in ['Wizzywise', 'BennieBliss']:
        keyboard = [
            [KeyboardButton("Wizzywise"), KeyboardButton("BennieBliss")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "❌ Please choose either 'Wizzywise' or 'BennieBliss' only.",
            reply_markup=reply_markup
        )
        return VOTING_VICE_PRESIDENT
    
    user_id = update.effective_user.id
    user_votes[user_id]['vice_president'] = vote
    
    await update.message.reply_text(
        "✅ Vote recorded!\n\n"
        "🏛️ **Question 3 of 6**\n"
        "**Rachel for Assistant General Secretary**\n"
        "Please vote: Yes or No",
        reply_markup=ReplyKeyboardRemove()
    )
    return VOTING_ASSISTANT_SECRETARY

async def handle_assistant_secretary_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle assistant secretary vote."""
    vote = update.message.text.strip().lower()
    
    if vote not in ['yes', 'no']:
        await update.message.reply_text(
            "❌ Please answer with 'Yes' or 'No' only.\n"
            "**Rachel for Assistant General Secretary** - Your vote:"
        )
        return VOTING_ASSISTANT_SECRETARY
    
    user_id = update.effective_user.id
    user_votes[user_id]['assistant_secretary'] = vote.capitalize()
    
    await update.message.reply_text(
        "✅ Vote recorded!\n\n"
        "🏛️ **Question 4 of 6**\n"
        "**Lionel for PRO**\n"
        "Please vote: Yes or No"
    )
    return VOTING_PRO

async def handle_pro_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PRO vote."""
    vote = update.message.text.strip().lower()
    
    if vote not in ['yes', 'no']:
        await update.message.reply_text(
            "❌ Please answer with 'Yes' or 'No' only.\n"
            "**Lionel for PRO** - Your vote:"
        )
        return VOTING_PRO
    
    user_id = update.effective_user.id
    user_votes[user_id]['pro'] = vote.capitalize()
    
    await update.message.reply_text(
        "✅ Vote recorded!\n\n"
        "🏛️ **Question 5 of 6**\n"
        "**Marvellous for D.O Socials**\n"
        "Please vote: Yes or No"
    )
    return VOTING_DO_SOCIALS

async def handle_do_socials_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle DO Socials vote."""
    vote = update.message.text.strip().lower()
    
    if vote not in ['yes', 'no']:
        await update.message.reply_text(
            "❌ Please answer with 'Yes' or 'No' only.\n"
            "**Marvellous for D.O Socials** - Your vote:"
        )
        return VOTING_DO_SOCIALS
    
    user_id = update.effective_user.id
    user_votes[user_id]['do_socials'] = vote.capitalize()
    
    await update.message.reply_text(
        "✅ Vote recorded!\n\n"
        "🏛️ **Question 6 of 6**\n"
        "**AbleGod for D.O Sports**\n"
        "Please vote: Yes or No"
    )
    return VOTING_DO_SPORTS

async def handle_do_sports_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle DO Sports vote and complete voting."""
    vote = update.message.text.strip().lower()
    
    if vote not in ['yes', 'no']:
        await update.message.reply_text(
            "❌ Please answer with 'Yes' or 'No' only.\n"
            "**AbleGod for D.O Sports** - Your vote:"
        )
        return VOTING_DO_SPORTS
    
    user_id = update.effective_user.id
    user_votes[user_id]['do_sports'] = vote.capitalize()
    
    # Store all votes in Google Sheets
    sheet = context.user_data.get('sheet')
    if sheet:
        success = store_vote(
            sheet, 
            update.effective_user.id,
            context.user_data['email'],
            context.user_data['name'],
            user_votes[user_id]
        )
        
        if success:
            await update.message.reply_text(
                "🎉 **Voting Complete!**\n\n"
                "Thank you for participating in the election. Your votes have been recorded successfully.\n\n"
                "📊 **Your Votes Summary:**\n"
                f"• TtED for President: {user_votes[user_id]['president']}\n"
                f"• Vice President: {user_votes[user_id]['vice_president']}\n"
                f"• Rachel for Assistant General Secretary: {user_votes[user_id]['assistant_secretary']}\n"
                f"• Lionel for PRO: {user_votes[user_id]['pro']}\n"
                f"• Marvellous for D.O Socials: {user_votes[user_id]['do_socials']}\n"
                f"• AbleGod for D.O Sports: {user_votes[user_id]['do_sports']}\n\n"
                "Your participation in this democratic process is valued!"
            )
        else:
            await update.message.reply_text(
                "❌ There was an error saving your votes. Please contact the administrator."
            )
    else:
        await update.message.reply_text(
            "❌ System error. Please contact the administrator."
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the voting process."""
    user_id = update.effective_user.id
    if user_id in user_votes:
        del user_votes[user_id]
    
    await update.message.reply_text(
        "🚫 Voting cancelled. You can start again anytime with /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    await update.message.reply_text(
        "🗳️ **Election Voting Bot Help**\n\n"
        "**Commands:**\n"
        "/start - Begin the voting process\n"
        "/cancel - Cancel current voting session\n"
        "/help - Show this help message\n\n"
        "**Voting Process:**\n"
        "1. Enter your registered email\n"
        "2. Enter your full name\n"
        "3. Enter your verification code\n"
        "4. Answer all 6 election questions\n"
        "5. Your votes will be recorded\n\n"
        "**Note:** You can only vote once per election."
    )

def main():
    """Run the bot."""
    # Create conversation handler
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
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    
    # Run the bot
    print("🤖 Election Voting Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

