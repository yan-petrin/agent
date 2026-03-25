import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import database as db
from agent import AgencyAgent

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

agent = AgencyAgent()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я агент управления агентством.\n\n"
        "Я могу помочь:\n"
        "• Создавать и отслеживать задачи\n"
        "• Управлять исполнителями и дедлайнами\n"
        "• Генерировать сводные отчёты\n\n"
        "Просто напиши что нужно сделать.\n"
        "Например: «Создай задачу "Подготовить презентацию" для Ивана до 2026-04-01»"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = agent.chat(user_id, user_message)
        # Escape any markdown that could break formatting
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error processing message for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз.")


def main():
    db.init_db()
    logger.info("Database initialized")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен. Добавь его в файл .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Агент запущен. Ожидание сообщений...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
