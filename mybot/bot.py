import asyncio
import sqlite3
import logging
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Document, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "7485175242:AAGvI_ubPhjACTNl_YOXDrl-3ROzzcWJcUQ"
ADMIN_ID = 949263879

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect('books.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author TEXT,
        category TEXT,
        file_id TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS access (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        allowed INTEGER,
        last_request_time INTEGER
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        name TEXT PRIMARY KEY
    )
''')
conn.commit()
conn.close()

# Проверка доступа
def check_access(user_id):
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT allowed FROM access WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

# Главное меню клавиатуры
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Библиотека")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT allowed, last_request_time FROM access WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        now = int(time.time())
        cursor.execute("INSERT INTO access (user_id, username, allowed, last_request_time) VALUES (?, ?, ?, ?)",
                       (user_id, username, 0, now))
        conn.commit()

    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu)

    if user_id == ADMIN_ID:
        admin_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить книгу", callback_data="add_book")],
                [InlineKeyboardButton(text="📂 Добавить категорию", callback_data="add_category")],
                [InlineKeyboardButton(text="🗑 Удалить категорию", callback_data="delete_category")]
            ]
        )
        await message.answer("🔧 Админ-панель:", reply_markup=admin_keyboard)

    conn.close()

@dp.message(lambda m: m.text == "ℹ️ Информация")
async def info_message(message: Message):
    text = (
        "🎓 Добро пожаловать к учителю Санат Сархатович !\n"
        "Здесь тебя обучат математике на узбекском и на русском языке.\n\n"
        "📚 Что мы предлагаем: Курсы математики для поступлении в университеты и для экзаменов SAT\n\n"
        "🎯 Подготовка к экзаменам\n"
        "➗ Математика для школьников и студентов\n"
        "💻🏫 Онлайн и офлайн занятия"
    )
    await message.answer(text)

@dp.message(lambda m: m.text == "📚 Библиотека")
async def categories_shortcut(message: Message):
    await show_categories(message)

@dp.callback_query(F.data == "request_access")
async def request_access(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "Без username"
    now = int(time.time())

    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT allowed, last_request_time FROM access WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row:
        last_request_time = row[1]
        if row[0] == -1 and now - last_request_time < 1800:
            await callback.answer("Вы можете повторно запросить доступ через 30 минут.", show_alert=True)
            conn.close()
            return
        cursor.execute("UPDATE access SET allowed=0, last_request_time=? WHERE user_id=?", (now, user_id))
    else:
        cursor.execute("INSERT INTO access (user_id, username, allowed, last_request_time) VALUES (?, ?, ?, ?)",
                       (user_id, username, 0, now))

    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Разрешить", callback_data=f"allow_{user_id}"),
             InlineKeyboardButton(text="❌ Запретить", callback_data=f"deny_{user_id}")]
        ]
    )

    await bot.send_message(
        ADMIN_ID,
        f"👤 Пользователь [@{username}](tg://user?id={user_id}) запросил доступ.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    await callback.answer("Запрос отправлен администратору.", show_alert=True)

@dp.callback_query(F.data.startswith("allow_"))
async def allow_user(callback: CallbackQuery):
    user_id = int(callback.data.replace("allow_", ""))
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE access SET allowed=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await bot.send_message(user_id, "✅ Вам разрешено использовать бота. Введите /start, чтобы начать.")
    await callback.answer("Разрешение выдано.")

@dp.callback_query(F.data.startswith("deny_"))
async def deny_user(callback: CallbackQuery):
    user_id = int(callback.data.replace("deny_", ""))
    now = int(time.time())
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE access SET allowed=-1, last_request_time=? WHERE user_id=?", (now, user_id))
    conn.commit()
    conn.close()
    await bot.send_message(user_id, "⛔️ Вам отказано в доступе. Повторный запрос через 30 минут.")
    await callback.answer("Запрос отклонён.")

@dp.callback_query(F.data == "add_book")
async def prompt_upload_book(callback: CallbackQuery):
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    categories = cursor.fetchall()
    conn.close()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=cat[0], callback_data=f"choose_category_{cat[0]}")] for cat in categories]
    )
    await callback.message.answer("📂 В какую категорию вы хотите добавить книгу?", reply_markup=keyboard)
    await callback.answer()

upload_temp = {}

@dp.callback_query(F.data.startswith("choose_category_"))
async def choose_category(callback: CallbackQuery):
    category = callback.data.replace("choose_category_", "")
    upload_temp[callback.from_user.id] = category
    await callback.message.answer(f"📤 Теперь отправьте файл книги для категории: {category}")
    await callback.answer()

@dp.message(lambda message: message.document and message.from_user.id == ADMIN_ID)
async def handle_uploaded_book(message: Message):
    category = upload_temp.get(message.from_user.id)
    if not category:
        await message.answer("⚠️ Сначала выберите категорию через кнопку 'Добавить книгу'.")
        return
    file = message.document
    file_id = file.file_id
    title = file.file_name.rsplit('.', 1)[0]
    author = "Неизвестен"
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO books (title, author, category, file_id) VALUES (?, ?, ?, ?)",
                   (title, author, category, file_id))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Книга '{title}' добавлена в категорию '{category}'.")
    upload_temp.pop(message.from_user.id, None)

@dp.message(Command("categories"))
async def show_categories(message: Message):
    if not check_access(message.from_user.id):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📩 Запросить разрешение", callback_data="request_access")]]
        )
        await message.answer("⛔️ У вас нет разрешения на использование бота.", reply_markup=keyboard)
        return
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    categories = cursor.fetchall()
    conn.close()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=cat[0], callback_data=f"show_books_{cat[0]}")] for cat in categories]
    )
    await message.answer("📚 Выберите категорию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("show_books_"))
async def show_books(callback: CallbackQuery):
    category = callback.data.replace("show_books_", "")
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM books WHERE category=?", (category,))
    books = cursor.fetchall()
    conn.close()

    # Показываем выбранную категорию
    await callback.message.answer(f"📂 Вы выбрали категорию: *{category}*", parse_mode="Markdown")

    if not books:
        await callback.message.answer("😕 В этой категории пока нет книг.")
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=title[0], callback_data=f"get_book_{title[0]}")] for title in books
            ]
        )
        await callback.message.answer("📘 Книги в этой категории:", reply_markup=keyboard)

    await callback.answer()

@dp.callback_query(F.data.startswith("get_book_"))
async def send_book(callback: CallbackQuery):
    title = callback.data.replace("get_book_", "")
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM books WHERE title=?", (title,))
    result = cursor.fetchone()
    conn.close()

    if result:
        file_id = result[0]
        await bot.send_document(callback.from_user.id, file_id, caption=title)
    else:
        await callback.message.answer("❌ Книга не найдена.")
    await callback.answer()

@dp.callback_query(F.data == "add_category")
async def prompt_add_category(callback: CallbackQuery):
    await callback.message.answer("Введите название новой категории:")
    upload_temp[callback.from_user.id] = "awaiting_category_name"
    await callback.answer()

@dp.message(lambda m: upload_temp.get(m.from_user.id) == "awaiting_category_name")
async def handle_new_category(message: Message):
    category = message.text.strip()
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Категория '{category}' добавлена.")
    upload_temp.pop(message.from_user.id)

@dp.callback_query(F.data == "delete_category")
async def prompt_delete_category(callback: CallbackQuery):
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    categories = cursor.fetchall()
    conn.close()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=cat[0], callback_data=f"confirm_delete_{cat[0]}")] for cat in categories]
    )
    await callback.message.answer("🗑 Выберите категорию для удаления:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_category(callback: CallbackQuery):
    category = callback.data.replace("confirm_delete_", "")
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE name=?", (category,))
    cursor.execute("DELETE FROM books WHERE category=?", (category,))
    conn.commit()
    conn.close()
    await callback.message.answer(f"❌ Категория '{category}' и все её книги удалены.")
    await callback.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())