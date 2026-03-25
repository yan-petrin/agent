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
        "Привет! Я агент агентства Hol для управления блогерами.\n\n"
        "Что умею:\n"
        "• Вести базу блогеров (контакты, платформы, охват, статусы, оплаты)\n"
        "• Переводить сообщения с португальского бразильского и обратно\n"
        "• Анализировать переписку и создавать задачи\n"
        "• Управлять кампаниями и этапами\n"
        "• Работать с Google Sheets, Docs, Drive и Gmail\n\n"
        "Примеры команд:\n"
        "— «Добавь блогера Марсела Силва, инстаграм @marcela, 80k подписчиков, ниша beauty»\n"
        "— «Переведи: Olá, temos interesse em trabalhar com você...»\n"
        "— «Напиши блогеру сообщение о нашем предложении по кампании X»\n"
        "— «Покажи всех активных блогеров»\n"
        "— «Создай отчёт по кампании #1 и сохрани в Docs»"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = agent.chat(user_id, user_message)
        # Split long messages (Telegram limit: 4096 chars)
        for chunk in _split(response, 4000):
            await update.message.reply_text(chunk)
    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз.")


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def main():
    db.init_db()
    logger.info("Database initialized: hol_agency.db")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Агент Hol запущен.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
