import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 7436283720  # Ваш Telegram ID   
DATA_FILE = "user_data.json"  # Файл для хранения данных

# Функции для работы с JSON-файлом
def load_data():
    """Загружает данные из JSON-файла."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_data(data):
    """Сохраняет данные в JSON-файл."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

# Загружаем данные из файла
user_data = load_data()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Поддержка", callback_data="support")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Путь к изображению
    file_path = os.path.abspath("ForTelegram.png")

    if os.path.exists(file_path):
        with open(file_path, "rb") as image_file:
            photo = InputFile(image_file)

            await update.message.reply_photo(
                photo,
                caption="Добро пожаловать в SoftHelper!\nНажмите на кнопку ниже, чтобы связаться с поддержкой.",
                reply_markup=reply_markup,
            )
    else:
        await update.message.reply_text("Изображение не найдено. Пожалуйста, проверьте файл.")

# Обработка нажатия кнопки
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Если нажата кнопка "Поддержка"
    if callback_data == "support":
        await query.message.reply_text("Как я могу помочь? Пожалуйста, напишите свой вопрос в одном сообщении и желательно подробно, так нашей поддержке будет легче помочь вам.")

    # Если это кнопка для ответа
    elif callback_data.startswith("reply_"):
        user_id = callback_data.split("_")[1]
        user_entry = next((user for user in user_data if user["user_id"] == int(user_id)), None)

        if user_entry:
            # Запрашиваем ответ у администратора
            await query.message.reply_text(f"Введите ваш ответ для пользователя @{user_entry['username']}:")
            context.user_data["reply_to_user"] = int(user_id)  # Сохраняем ID пользователя для ответа
        else:
            await query.message.reply_text("Пользователь не найден.")

# Обработка сообщений от администратора для ответа
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    if "reply_to_user" in context.user_data:
        user_id = context.user_data["reply_to_user"]
        user_entry = next((user for user in user_data if user["user_id"] == user_id), None)

        if user_entry:
            # Отправляем ответ пользователю
            await context.bot.send_message(
                chat_id=user_id,
                text=update.message.text
            )

            # Обновляем статус пользователя
            user_entry["status"] = "resolved"
            save_data(user_data)  # Сохраняем изменения

            await update.message.reply_text(f"✅ Ответ отправлен пользователю @{user_entry['username']}.")
            del context.user_data["reply_to_user"]
        else:
            await update.message.reply_text("Пользователь не найден.")
    else:
        await update.message.reply_text("Вы не выбрали пользователя для ответа. Нажмите кнопку для ответа на запрос.")

# Получение сообщения от пользователя
async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    username = update.message.chat.username or update.message.chat.first_name
    message = update.message.text

    # Проверяем, может ли пользователь отправить сообщение
    user_entry = next((user for user in user_data if user["user_id"] == user_id), None)
    if user_entry and user_entry.get("status") != "can_message":
        await update.message.reply_text("Вы уже отправили сообщение. Ожидайте ответа поддержки.")
        return

    # Сохраняем сообщение и обновляем статус на "awaiting_reply"
    if user_entry:
        user_entry["last_message"] = message
        user_entry["status"] = "awaiting_reply"
    else:
        user_entry = {
            "user_id": user_id,
            "username": username,
            "last_message": message,
            "status": "awaiting_reply",
        }
        user_data.append(user_entry)

    save_data(user_data)  # Сохраняем изменения

    # Уведомляем администратора
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новое сообщение от @{username}:\n\n{message}\n\nОтветьте командой:\n/reply {user_id} ваш_ответ",
    )

    await update.message.reply_text("Спасибо за ваше сообщение! Постараемся ответить вам как можно быстрее :)")

# Ответ администратором
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используйте формат: /reply <user_id> <ответ>")
        return

    user_id = args[0]
    reply_message = " ".join(args[1:])

    # Отправляем ответ пользователю
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"{reply_message}")
        await update.message.reply_text("✅ Ответ отправлен пользователю.")

        # Обновляем статус пользователя на "resolved"
        user_entry = next((user for user in user_data if user["user_id"] == int(user_id)), None)
        if user_entry:
            user_data.remove(user_entry)
            save_data(user_data)  # Сохраняем изменения

    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке сообщения: {str(e)}")

# Команда /list
async def list_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    # Оставляем только открытые запросы
    open_requests = [data for data in user_data if data.get("status") == "awaiting_reply"]

    if not open_requests:
        await update.message.reply_text("На данный момент нет открытых обращений.")
        return

    # Формируем ответ
    response = "Список обращений:\n\n"
    for request in open_requests:
        response += (
            f"Пользователь: @{request['username']} (ID: {request['user_id']})\n"
            f"Сообщение: {request['last_message']}\n\n"
        )

    await update.message.reply_text(response)

# Главная функция
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_message))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CommandHandler("list", list_requests))

    app.run_polling()

if __name__ == "__main__":
    main()
