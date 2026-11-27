
import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
]

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = "telegram"

# Store the relationship between admin messages and users
message_map = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# Welcome message
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Welcome to Anonymous Message Bot!\n\n"
    
        "Simply type your message or send a photo, video or document.\n\n"
        "Your Telegram identity will not be shown to the administrators."
    )


# Receive messages from users
async def receive_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    user_id = update.effective_user.id

    # Ignore messages from administrators
    if user_id in ADMIN_IDS:
        return

    delivered = 0

    for admin_id in ADMIN_IDS:

        try:
            # Copy the message without showing sender identity
            copied = await context.bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )

            # Remember which user sent this message
            message_map[(admin_id, copied.message_id)] = message.chat_id

            # Notify administrator
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    "📩 New anonymous message!\n\n"
                    "Reply directly to the copied message "
                    "to respond to the sender."
                ),
            )

            delivered += 1

        except Exception:
            logger.exception(
                "Failed to deliver message to admin %s",
                admin_id
            )

    if delivered == len(ADMIN_IDS):

        await message.reply_text(
            "✅ Your anonymous message was delivered to both administrators."
        )

    else:

        await message.reply_text(
            "⚠️ Your message could not be delivered to both administrators. "
            "Please try again later."
        )


# Handle administrator replies
async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    admin_id = update.effective_user.id

    if admin_id not in ADMIN_IDS:
        return

    if not message.reply_to_message:
        return

    original_message_id = message.reply_to_message.message_id

    sender_chat_id = message_map.get(
        (admin_id, original_message_id)
    )

    if not sender_chat_id:

        await message.reply_text(
            "❌ Cannot find the original sender. "
            "The reply mapping may have expired."
        )

        return

    try:

        # Copy the admin's reply to the original sender
        await context.bot.copy_message(
            chat_id=sender_chat_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

        await message.reply_text(
            "✅ Your reply was delivered."
        )

    except Exception:

        logger.exception("Failed to send administrator reply")

        await message.reply_text(
            "❌ Failed to deliver your reply."
        )


# Main application
def main():

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing from .env")

    if len(ADMIN_IDS) != 2:
        raise ValueError("You must configure exactly two ADMIN_IDS")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Register handlers
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.REPLY & ~filters.COMMAND,
            admin_reply
        )
    )

    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            receive_message
        )
    )

    # Local development: polling
    if not WEBHOOK_URL:

        print("Bot is running locally using polling...")

        application.run_polling()

    # Render deployment: webhook
    else:

        if not WEBHOOK_SECRET:
            raise ValueError("WEBHOOK_SECRET is missing")

        print("Bot is starting using webhook...")

        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
        )


if __name__ == "__main__":
    main()
