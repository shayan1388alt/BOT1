import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Secure environment variable handling
API_KEY = os.getenv('TELEGRAM_API_KEY')

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a command handler for the start command

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('سلام! من یک ربات تلگرام هستم.')

# Define a message handler for text messages

def echo(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)

# Error handling

def error(update: Update, context: CallbackContext) -> None:
    logger.error(f'Update {update} caused error {context.error}')

# Main function to start the bot

def main() -> None:
    # Create the Updater and pass it your bot's token
    updater = Updater(API_KEY)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Register command and message handlers
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
    dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you send a signal to stop
    updater.idle()

if __name__ == '__main__':
    main()