import logging
import os
import sqlite3
import shlex
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PAGE_SIZE = 3 
DB_PATH = 'ad_exchange.db'

def init_db():
    db_exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    if not db_exists:
        logging.info("Creating new database: %s", DB_PATH)
        try:
            c.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL CHECK(role IN ('advertiser', 'seller')),
                    username TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE ad_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    target_audience INTEGER NOT NULL CHECK(target_audience BETWEEN 1 AND 10000000),
                    tags TEXT NOT NULL,
                    price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            c.execute('''
                CREATE TABLE seller_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_link TEXT NOT NULL CHECK(channel_link GLOB '@*'),
                    channel_name TEXT NOT NULL,
                    price_per_post REAL NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            conn.commit()
            logging.info("Database tables created successfully")
        except sqlite3.Error as e:
            logger.error("Error creating tables: %s", e)
    else:
        logging.info("Using existing database: %s", DB_PATH)
    return conn

db_connection = init_db()

async def get_user_role(user_id: int) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    except sqlite3.Error as e:
        logger.error("DB get_user_role error: %s", e)
        return None
    finally:
        conn.close()
    return row[0] if row else None

async def register_user(user_id: int, username: str, role: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO users (user_id, role, username)
            VALUES (?, ?, ?)
        ''', (user_id, role, username))
        conn.commit()
    except sqlite3.Error as e:
        logger.error("DB register_user error: %s", e)
    finally:
        conn.close()

async def get_total_pages(table: str) -> int:
    if table not in ("ad_requests", "seller_channels"):
        raise ValueError("Invalid table name")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {table}")
        total = c.fetchone()[0]
    except sqlite3.Error as e:
        logger.error("DB get_total_pages error: %s", e)
        return 0
    finally:
        conn.close()
    return (total + PAGE_SIZE - 1) // PAGE_SIZE

async def format_records(records, table_type: str):
    formatted = []
    for rec in records:
        if table_type == "ad_requests":
            formatted.append(
                f"\n📝 Описание: {rec[1]}\n"
                f"👥 ЦА: {rec[2]} чел.\n"
                f"🏷️ Метки: {rec[3]}\n"
                f"💰 Цена: ${rec[4]:.2f}\n"
                f"👤 {rec[5]}\n"
                f"🆔 ID: {rec[0]}"
            )
        else:  # seller_channels
            formatted.append(
                f"\n📢 Канал: {rec[2]} ({rec[1]})\n"
                f"🏷️ Метки: {rec[3]}\n"
                f"💰 Цена: ${rec[4]:.2f}\n"
                f"👤 {rec[5]}\n"
                f"🆔 ID: {rec[0]}"
            )
    return "\n\n" + "═"*30 + "\n\n".join(formatted) + "\n\n" + "═"*30 if formatted else ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "Без username"
    current_role = await get_user_role(user_id)
    if current_role:
        await update.message.reply_text(
            f"С возвращением, {user.full_name}!\n"
            f"Ваша роль: {'рекламодатель' if current_role=='advertiser' else 'продавец'}\n"
            "Используйте /help"
        )
    else:
        keyboard = [[InlineKeyboardButton("Я рекламодатель", callback_data="role:advertiser")],
                    [InlineKeyboardButton("Я продавец каналов", callback_data="role:seller")]]
        await update.message.reply_text(
            "Добро пожаловать на биржу рекламы FindYourAd! Выберите роль:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = await get_user_role(user.id) or 'UNKWOWN'
    text = (
        "Справка по командам бота FindYourAd:\n\n"
        f"👤 Пользователь: {user.full_name} ({user.username or '—'})\n"
        f"🔖 Ваша роль: {role}\n\n"
        "📚 Общие команды:\n"
        "/start — запуск бота и выбор/смена роли.\n"
        "/help — эта справка.\n"
        "/set_role <advertiser|seller> — сменить роль.\n\n"
        "📝 Команды для рекламодателя (advertiser):\n"
        "/add_request 'Описание' АудиторияЧисло 'Метка1,Метка2' Цена — создать рекламный запрос.\n"
        "/view_channels — просмотреть список каналов.\n"
        "/my_requests — показать и удалить свои запросы.\n\n"
        "📺 Команды для продавца каналов (seller):\n"
        "/add_channel @канал 'Название' Цена 'Метка1,Метка2' — добавить свой канал.\n"
        "/view_requests — просмотреть запросы рекламодателей.\n"
        "/my_channels — показать и удалить свои каналы."
    )
    if role == 'advertiser':
        kb = [[InlineKeyboardButton("Сменить роль на продавца", callback_data='role:seller')],
              [InlineKeyboardButton("Просмотреть каналы", callback_data='chan_page:1')],
              [InlineKeyboardButton("Мои запросы", callback_data='my_requests')]]
    elif role == 'seller':
        kb = [[InlineKeyboardButton("Сменить роль на рекламодателя", callback_data='role:advertiser')],
              [InlineKeyboardButton("Просмотреть запросы", callback_data='req_page:1')],
              [InlineKeyboardButton("Мои каналы", callback_data='my_channels')]]
    else:
        kb = []
    if update.callback_query:
        await update.callback_query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(kb) if kb else None
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb) if kb else None)


async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] not in ('advertiser','seller'):
        return await update.message.reply_text("Используйте: /set_role advertiser или /set_role seller")
    new_role = context.args[0]
    user = update.effective_user
    await register_user(user.id, f"@{user.username}" if user.username else "", new_role)
    await help_command(update, context)

async def _get_message_obj(update: Update):
    return update.message or update.callback_query.message

async def add_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'advertiser':
        return await update.message.reply_text("Только рекламодатели могут добавлять запросы.")
    
    try:
        args = shlex.split(update.message.text)
        if len(args) < 5:
            return await update.message.reply_text(
                "Формат: /add_request 'Описание' АудиторияЧисло 'Метка1,Метка2' Цена"
            )
        desc = args[1]
        ca = int(args[2])
        tags = args[3].lower()
        price = float(args[4])

        if not (1 <= ca <= 1e7) or price <= 0:
            raise ValueError("Invalid CA or price")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO ad_requests (user_id, description, target_audience, tags, price) VALUES (?, ?, ?, ?, ?)',
                  (user.id, desc, ca, tags, price))
        conn.commit()
        conn.close()

        await update.message.reply_text("Запрос успешно добавлен!")
    except Exception as e:
        logger.error("add_request error: %s", e)
        await update.message.reply_text(
            "Ошибка при добавлении запроса. Убедитесь, что вы используете правильный формат: "
            "/add_request 'Описание' АудиторияЧисло 'Метка1,Метка2' Цена"
        )

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'seller':
        return await update.message.reply_text("Только продавцы могут добавлять каналы.")
    
    try:
        args = shlex.split(update.message.text)
        if len(args) < 5:
            return await update.message.reply_text(
                "Формат: /add_channel @канал 'Название' Цена 'Метка1,Метка2'"
            )
        
        link = args[1]
        name = args[2]
        price = float(args[3])
        tags = args[4].lower()

        if not link.startswith('@') or price <= 0:
            raise ValueError("Invalid channel link or price")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO seller_channels (user_id, channel_link, channel_name, price_per_post, tags) VALUES (?, ?, ?, ?, ?)',
                  (user.id, link, name, price, tags))
        conn.commit()
        conn.close()

        await update.message.reply_text("Канал успешно добавлен!")
    except Exception as e:
        logger.error("add_channel error: %s", e)
        await update.message.reply_text(
            "Ошибка при добавлении канала. Убедитесь, что вы используете правильный формат: "
            "/add_channel @канал 'Название' Цена 'Метка1,Метка2'"
        )
async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'seller':
        return await (await _get_message_obj(update)).reply_text("Только продавцы")
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    total = await get_total_pages('ad_requests')
    if page < 1 or page > total:
        page = 1
    offset = (page - 1) * PAGE_SIZE
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT ar.id,ar.description,ar.target_audience,ar.tags,ar.price,u.username
                   FROM ad_requests ar JOIN users u ON ar.user_id=u.user_id
                   LIMIT ? OFFSET ?''', (PAGE_SIZE, offset))
    recs = cur.fetchall()
    conn.close()
    if not recs:
        return await (await _get_message_obj(update)).reply_text("Нет запросов")

    msg = f"📋 Рекламные запросы (страница {page}/{total}):" + await format_records(recs, 'ad_requests')

    kb = []

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀ Назад", callback_data=f"req_page:{page-1}"))
    if page < total:
        nav_row.append(InlineKeyboardButton("Вперед ▶", callback_data=f"req_page:{page+1}"))

    if nav_row:
        kb.append(nav_row)

    kb.append([InlineKeyboardButton("Меню", callback_data="show_help")])

    await (await _get_message_obj(update)).reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))


async def view_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'advertiser':
        return await (await _get_message_obj(update)).reply_text("Только рекламодатели")
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    total = await get_total_pages('seller_channels')
    if page < 1 or page > total:
        page = 1
    offset = (page - 1) * PAGE_SIZE
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT sc.id,sc.channel_link,sc.channel_name,sc.tags,sc.price_per_post,u.username
                   FROM seller_channels sc JOIN users u ON sc.user_id=u.user_id
                   LIMIT ? OFFSET ?''', (PAGE_SIZE, offset))
    recs = cur.fetchall()
    conn.close()
    if not recs:
        return await (await _get_message_obj(update)).reply_text("Нет каналов")

    msg = f"📺 Каналы (страница {page}/{total}):" + await format_records(recs, 'seller_channels')

    kb = []

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀ Назад", callback_data=f"chan_page:{page-1}"))
    if page < total:
        nav_row.append(InlineKeyboardButton("Вперед ▶", callback_data=f"chan_page:{page+1}"))

    if nav_row:
        kb.append(nav_row)

    kb.append([InlineKeyboardButton("Меню", callback_data="show_help")])

    await (await _get_message_obj(update)).reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))


async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'advertiser':
        return await (await _get_message_obj(update)).reply_text("Только рекламодатели")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id,description,target_audience,tags,price FROM ad_requests WHERE user_id=?', (user.id,))
    recs = cur.fetchall()
    conn.close()
    if not recs:
        return await (await _get_message_obj(update)).reply_text("У вас нет запросов")
    msg = "📋 Ваши рекламные запросы:\n"
    for r in recs:
        msg += f"🆔{r[0]} Описание:{r[1]} ЦА:{r[2]} Цена:${r[4]:.2f}\n" + "═"*20 + "\n"
    kb = [[InlineKeyboardButton(f"❌ Удалить {r[0]}", callback_data=f"del_req:{r[0]}")] for r in recs]
    kb.append([InlineKeyboardButton("Меню", callback_data="show_help")])
    await (await _get_message_obj(update)).reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def my_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await get_user_role(user.id) != 'seller':
        return await (await _get_message_obj(update)).reply_text("Только продавцы")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id,channel_link,channel_name,tags,price_per_post FROM seller_channels WHERE user_id=?', (user.id,))
    recs = cur.fetchall()
    conn.close()
    if not recs:
        return await (await _get_message_obj(update)).reply_text("У вас нет каналов")
    msg = "📺 Ваши каналы:\n"
    for r in recs:
        msg += f"🆔{r[0]} {r[2]}({r[1]}) Цена:${r[4]:.2f}\n" + "═"*20 + "\n"
    kb = [[InlineKeyboardButton(f"❌ Удалить {r[0]}", callback_data=f"del_chan:{r[0]}")] for r in recs]
    kb.append([InlineKeyboardButton("Меню", callback_data="show_help")])
    await (await _get_message_obj(update)).reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    if ':' in query.data:
        action, val = query.data.split(':', maxsplit=1)
    else:
        action = query.data
        val = None

    if action == 'role' and val:
        context.args = [val]
        await set_role(update, context)

    elif action == 'req_page' and val:
        context.args = [val]
        await view_requests(update, context)

    elif action == 'chan_page' and val:
        context.args = [val]
        await view_channels(update, context)
    elif action == 'my_requests':
        await my_requests(update, context)
    elif action == 'my_channels':
        await my_channels(update, context)

    elif action == 'del_req' and val:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM ad_requests WHERE id=? AND user_id=?', (int(val), query.from_user.id))
        conn.commit()
        conn.close()
        await query.message.reply_text(f"✅ Запрос ID:{val} удалён!")
        await my_requests(update, context)

    elif action == 'del_chan' and val:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM seller_channels WHERE id=? AND user_id=?', (int(val), query.from_user.id))
        conn.commit()
        conn.close()
        await query.message.reply_text(f"✅ Канал ID:{val} удалён!")
        await my_channels(update, context)
    elif action == 'show_help':
        await help_command(update, context)

    try:
        await query.message.delete()
    except:
        pass


def main():
    """Запуск бота"""
    application = Application.builder().token("TOKEN").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("set_role", set_role))
    application.add_handler(CommandHandler("add_request", add_request))
    application.add_handler(CommandHandler("add_channel", add_channel))
    application.add_handler(CommandHandler("view_requests", view_requests))
    application.add_handler(CommandHandler("view_channels", view_channels))
    application.add_handler(CommandHandler("my_requests", my_requests))
    application.add_handler(CommandHandler("my_channels", my_channels))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.run_polling()

if __name__ == "__main__":
    main()
