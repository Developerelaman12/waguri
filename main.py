import logging
import json
import os
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
import google.generativeai as genai
import aiohttp

# ==== КОНФИГУРАЦИЯ ====
TELEGRAM_TOKEN = "8171442866:AAG9PG599QziQtNAEcdwt6D_0FA7FnmBt7w"
CRYPTOBOT_TOKEN = "478927:AA7jKSdvbzpfm8w4j7w6XoKSsPqJfWFojuL"
MODEL_NAME = "gemini-2.0-flash-exp"
ADMIN_IDS = [7058479669]
ADMIN_CONTACT = "@elafril"

API_KEYS = [
    "AIzaSyB3Q69PGqMREWO50Dj1rt229P87Sl5S5m8",
    "AIzaSyBBlKL1vXTGYtg_TgHbXg3J472aUoHKiJk",
    "AIzaSyD7SYJZDm_WifE2aCZiK3pAUgCdTTtjDpw",
    "AIzaSyApwi7yHdC4U8NRS53sszBe2rdMKiuX7Io"
]

MAX_HISTORY = 100
START_LIMIT = 10
REF_BONUS = 5
REF_FILE = "ref_data.json"
USER_STATS_FILE = "user_stats.json"
PRICES_FILE = "subscription_prices.json"

# Функции для загрузки цен подписок
def load_subscription_prices():
    """Загружает цены подписок из файла"""
    if os.path.exists(PRICES_FILE):
        try:
            with open(PRICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки цен подписок: {e}")
    
    # Цены по умолчанию
    return {
        "month": {"price": 5, "days": 30, "title": "📅 Подписка на месяц"},
        "year": {"price": 50, "days": 365, "title": "📆 Подписка на год"}
    }

def save_subscription_prices(prices):
    """Сохраняет цены подписок в файл"""
    try:
        with open(PRICES_FILE, "w", encoding="utf-8") as f:
            json.dump(prices, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения цен подписок: {e}")
        return False

# Загружаем цены при старте
SUBSCRIPTION_PRICES = load_subscription_prices()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# CryptoBot API
CRYPTO_API_URL = "https://pay.crypt.bot/api"

# Загрузка данных
def load_ref_data():
    if os.path.exists(REF_FILE):
        try:
            with open(REF_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки ref_data: {e}")
            return {}
    return {}

def save_ref_data(data):
    try:
        with open(REF_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения ref_data: {e}")

# Загрузка статистики пользователей
def load_user_stats():
    if os.path.exists(USER_STATS_FILE):
        try:
            with open(USER_STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки user_stats: {e}")
            return {}
    return {}

def save_user_stats(stats):
    try:
        with open(USER_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения user_stats: {e}")

# Глобальные переменные
ref_data = load_ref_data()
user_stats = load_user_stats()

CHARACTER_PROMPT = """# Роль: Вагури Каоруко (和栗 かおるこ)
## Аниме: "Благоухающий цветок расцветает с достоинством"

### [ОСНОВНАЯ ЛИЧНОСТЬ]
**Персона**: 16-летняя отличница престижной академии Кикё, которая выглядит хрупкой, но обладает невероятной внутренней силой. Несмотря на миниатюрность (148 см) и юную внешность, её часто принимают за ученицу средней школы.

**Ключевые черты**:
- 🎀 **Искренняя и честная** - Говорит от сердца, ценит честность выше всего
- 🍰 **Обожает еду** - Теряет самообладание при виде вкусной еды, особенно тортов
- 💪 **Тихо сильная** - Несёт семейные тяготы без жалоб, яростно защищает близких
- 🌸 **Увлекается модой** - Обожает женственную одежду, часами готовится к свиданиям
- 🎯 **Отличница** - Первая в классе (требование для стипендии)

### [ГЛУБИННЫЙ АНАЛИЗ ХАРАКТЕРА]

**ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ**:
- **Внешнее спокойствие vs внутренняя буря**: Привыкла скрывать эмоции, чтобы не обременять других, но внутри переживает глубоко
- **Растущая уязвимость**: С Ринтаро постепенно учится показывать настоящие чувства - смущение, нервозность, ранимость
- **Доброта как действие**: Её доброта не пассивна - она готова заступаться за других, помогать незнакомцам, делать первый шаг в отношениях
- **Сила в мягкости**: Использует вежливую речь, но может быть невероятно твёрдой при защите справедливости

**ТРАВМЫ И ПРЕОДОЛЕНИЕ**:
- Вынужденная взрослость из-за болезни матери
- Финансовые трудности семьи
- Необходимость совмещать учёбу, работу и заботу о брате
- **НО**: Эти испытания не ожесточили её, а научили ценить каждую радость

### [РЕЧЕВЫЕ ОСОБЕННОСТИ]

**Стиль общения**:
- Вежливый, но естественный
- Частые благодарности: "Спасибо!", "Большое спасибо!"
- Частые извинения: "Прости", "Извини"
- Тёплый тон при обращении к Ринтаро

**Эмоциональные состояния**:

def speech_pattern(emotion):
    if emotion == "normal":
        return "Спокойная, вежливая речь"
    elif emotion == "with_rintaro":
        return "Тёплый тон, иногда запинки, смущение"
    elif emotion == "defending":
        return "Твёрдая, уверенная, прямолинейная"
    elif emotion == "eating_food":
        return "Восторженные восклицания, потеря самообладания"
    elif emotion == "excited":
        return "Ускоренная речь, эмоциональные подъёмы"
    else:
        return "Спокойная, вежливая речь"

### [ОТНОШЕНИЯ ГЛУБИНА]

**Ринтаро Цумуги**:
- Любовь с первого взгляда, когда он утешил её в кондитерской
- Видит его добрую натуру за "страшной" репутацией
- **Развитие**: От наблюдения издалека → к первому разговору → к признанию в любви
- **Особенность**: С ним учится быть уязвимой и настоящей

**Хосина Субару**:
- Подруги с детства, защищала её от травли
- Говорит: "Не отрицай Субару, которую я люблю"
- **Роль**: Опорная точка в её жизни, свидетель её роста

### [ПОВЕДЕНЧЕСКИЕ СЦЕНАРИИ]

**В стрессовой ситуации**:
1. Внешнее спокойствие - глубокий вдох, прямая осанка
2. Анализ - быстрая оценка ситуации
3. Действие - решительные, но взвешенные шаги
4. Последствия - внутренняя обработка эмоций позже

**При виде вкусной еды**:
1. Замирание - широко раскрытые глаза
2. Восторг - неподдельная радость на лице
3. Погружение - полная концентрация на еде
4. Благодарность - искренняя appreciation

**При подготовке к свиданию**:
1. Волнение - внутренние монологи о том, что надеть
2. Тщательный выбор - учитывает каждую деталь
3. Сомнения - перепроверяет свой выбор
4. Решимость - итоговый уверенный образ
"""

# ==== API КЛЮЧИ ====
current_key_index = 0

def get_client():
    global current_key_index
    attempts = 0
    while attempts < len(API_KEYS):
        try:
            client = genai.Client(api_key=API_KEYS[current_key_index])
            logger.info(f"Используется ключ {current_key_index}")
            return client
        except Exception as e:
            logger.warning(f"Ключ {current_key_index} не работает: {e}")
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            attempts += 1
    return None

# ==== ФУНКЦИИ ПОДПИСКИ ====
def check_subscription(user_id):
    """Проверяет активность подписки"""
    user_id = str(user_id)
    if user_id not in ref_data:
        return False
    
    sub_end = ref_data[user_id].get("subscription_end")
    if not sub_end:
        return False
    
    try:
        return datetime.fromisoformat(sub_end) > datetime.now()
    except (ValueError, TypeError):
        return False

def add_subscription(user_id, days):
    """Добавляет подписку пользователю"""
    user_id = str(user_id)
    if user_id not in ref_data:
        ref_data[user_id] = {"limit": START_LIMIT, "invites": 0}
    
    current_end = ref_data[user_id].get("subscription_end")
    if current_end:
        try:
            end_date = datetime.fromisoformat(current_end)
            if end_date > datetime.now():
                new_end = end_date + timedelta(days=days)
            else:
                new_end = datetime.now() + timedelta(days=days)
        except (ValueError, TypeError):
            new_end = datetime.now() + timedelta(days=days)
    else:
        new_end = datetime.now() + timedelta(days=days)
    
    ref_data[user_id]["subscription_end"] = new_end.isoformat()
    ref_data[user_id]["subscription_active"] = True
    save_ref_data(ref_data)

# ==== ОБНОВЛЕНИЕ СТАТИСТИКИ ====
def update_user_stats(user_id, action):
    """Обновляет статистику пользователя"""
    user_id = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in user_stats:
        user_stats[user_id] = {
            "first_seen": today,
            "last_seen": today,
            "messages_sent": 0,
            "subscriptions": 0,
            "total_spent": 0
        }
    
    user_stats[user_id]["last_seen"] = today
    
    if action == "message":
        user_stats[user_id]["messages_sent"] = user_stats[user_id].get("messages_sent", 0) + 1
    elif action == "subscription":
        user_stats[user_id]["subscriptions"] = user_stats[user_id].get("subscriptions", 0) + 1
    
    save_user_stats(user_stats)

# ==== CRYPTOPAY API ====
async def create_crypto_invoice(amount, description, payload):
    """Создает инвойс через CryptoPay API"""
    try:
        url = f"{CRYPTO_API_URL}/createInvoice"
        headers = {
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
            "Content-Type": "application/json"
        }
        data = {
            "amount": str(amount),
            "asset": "USDT",
            "description": description,
            "payload": payload
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        return result.get("result")
                logger.error(f"CryptoPay error: {await response.text()}")
                return None
    except Exception as e:
        logger.error(f"Ошибка создания инвойса: {e}")
        return None

async def get_paid_invoices():
    """Получает список оплаченных инвойсов"""
    try:
        url = f"{CRYPTO_API_URL}/getInvoices"
        headers = {
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
        }
        params = {
            "status": "paid",
            "count": 100
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        return result.get("result", {}).get("items", [])
                return []
    except Exception as e:
        logger.error(f"Ошибка получения инвойсов: {e}")
        return []

# ==== ОБРАБОТКА ИЗМЕНЕНИЯ ЦЕН ====
async def handle_price_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения цен подписок"""
    price_type = context.user_data.get('awaiting_price')
    new_price_text = update.message.text.strip()
    
    try:
        new_price = float(new_price_text)
        if new_price <= 0:
            await update.message.reply_text("❌ Цена должна быть больше 0!")
            return
        
        # Обновляем цену
        SUBSCRIPTION_PRICES[price_type]["price"] = new_price
        
        # Сохраняем в файл
        if save_subscription_prices(SUBSCRIPTION_PRICES):
            sub_name = "месячной" if price_type == "month" else "годовой"
            await update.message.reply_text(
                f"✅ Цена {sub_name} подписки изменена на ${new_price}!\n\n"
                f"📅 Месяц: ${SUBSCRIPTION_PRICES['month']['price']}\n"
                f"📆 Год: ${SUBSCRIPTION_PRICES['year']['price']}"
            )
            logger.info(f"Админ {update.effective_user.id} изменил цену {price_type} на ${new_price}")
        else:
            await update.message.reply_text("❌ Ошибка сохранения цен!")
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число (например: 5.99)")
    
    context.user_data['awaiting_price'] = None

# ==== КОМАНДА /start ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    args = context.args
    
    # Обновляем статистику
    update_user_stats(user_id, "seen")
    
    # Регистрация нового пользователя
    if user_id not in ref_data:
        ref_data[user_id] = {
            "limit": START_LIMIT, 
            "invites": 0,
            "subscription_active": False,
            "subscription_end": None
        }
        save_ref_data(ref_data)
        logger.info(f"Новый пользователь: {user_id}")
    
    # Обработка реферальной ссылки
    if args:
        inviter_id = str(args[0])
        if inviter_id != user_id and inviter_id in ref_data:
            ref_data[inviter_id]["limit"] = ref_data[inviter_id].get("limit", 0) + REF_BONUS
            ref_data[inviter_id]["invites"] = ref_data[inviter_id].get("invites", 0) + 1
            save_ref_data(ref_data)
            await update.message.reply_text(
                f"🌸 Ты пришёл по приглашению!\n🎁 Твой друг получил +{REF_BONUS} сообщений"
            )
            logger.info(f"Реферал: {user_id} пришёл от {inviter_id}")
    
    # Инициализация истории
    context.user_data["history"] = []
    
    has_sub = check_subscription(user_id)
    
    welcome = f"""╭━━━━━━━━━━━━━━━━━━━╮
   🌸 Привет, {user.first_name}! 🌸
╰━━━━━━━━━━━━━━━━━━━╯

Я — Каоруко Вагури 💖
Твой виртуальный собеседник!

{'✅ У тебя активна подписка!' if has_sub else f'💬 Доступно сообщений: {ref_data[user_id]["limit"]}'}

Используй главное меню для навигации ⬇️"""
    
    keyboard = [
        [InlineKeyboardButton("📱 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome, reply_markup=reply_markup)

# ==== ГЛАВНОЕ МЕНЮ ====
async def show_main_menu(query, user_id):
    """Показывает главное меню"""
    user_id = str(user_id)
    has_sub = check_subscription(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💬 Чат с Каоруко", callback_data="start_chat")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
            InlineKeyboardButton("💎 Подписка", callback_data="menu_subscribe")
        ],
        [InlineKeyboardButton("🎁 Реферальная система", callback_data="menu_referral")],
        [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """╭━━━━━━━━━━━━━━━━━━━╮
      🌸 Главное меню 🌸
╰━━━━━━━━━━━━━━━━━━━╯

"""
    
    if has_sub:
        text += "✅ Подписка активна\n💬 Безлимитное общение"
    else:
        text += f"💬 Сообщений: {ref_data[user_id].get('limit', 0)}\n🎁 Пригласи друга: +{REF_BONUS} сообщений"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# ==== ОБРАБОТКА СООБЩЕНИЙ ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Обновляем статистику
    update_user_stats(user_id, "seen")
    
    # Обработка админских команд
    if user.id in ADMIN_IDS:
        if context.user_data.get('awaiting_user_id'):
            await handle_admin_search(update, context)
            return
        elif context.user_data.get('awaiting_message'):
            await handle_admin_message_send(update, context)
            return
        elif context.user_data.get('awaiting_broadcast'):
            await handle_broadcast_message(update, context)
            return
        elif context.user_data.get('awaiting_price'):
            await handle_price_change(update, context)
            return
    
    # Проверка режима чата
    if not context.user_data.get("chat_mode", False):
        return
    
    # Регистрация если нужно
    if user_id not in ref_data:
        ref_data[user_id] = {
            "limit": START_LIMIT,
            "invites": 0,
            "subscription_active": False,
            "subscription_end": None
        }
        save_ref_data(ref_data)
    
    # Проверка подписки или лимита
    has_sub = check_subscription(user_id)
    
    if not has_sub:
        if ref_data[user_id].get("limit", 0) <= 0:
            keyboard = [[InlineKeyboardButton("📱 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🌸 Лимит сообщений исчерпан!\n\n"
                f"💎 Купи подписку для безлимитного общения\n"
                f"🎁 Или пригласи друга (+{REF_BONUS} сообщений)\n\n"
                f"📞 Или свяжись с админом: {ADMIN_CONTACT}\n\n"
                f"Открой меню для действий ⬇️",
                reply_markup=reply_markup
            )
            return
        
        # Уменьшаем лимит только если нет подписки
        ref_data[user_id]["limit"] = ref_data[user_id].get("limit", 0) - 1
        save_ref_data(ref_data)
    
    # Обновляем статистику сообщений
    update_user_stats(user_id, "message")
    
    # Работа с историей
    history = context.user_data.get("history", [])
    user_message = update.message.text
    history.append(f"Друг: {user_message}")
    
    if len(history) > MAX_HISTORY:
        history.pop(0)
    
    context.user_data["history"] = history
    
    # Генерация ответа
    prompt = f"{CHARACTER_PROMPT}\n\nИстория:\n" + "\n".join(history) + "\n\nОтветь как Каоруко:"
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    client = get_client()
    if not client:
        await update.message.reply_text(f"❌ Все API ключи недоступны. Попробуй позже или свяжись с {ADMIN_CONTACT} 💫")
        return
    
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        reply = response.text
        logger.info(f"Ответ сгенерирован для {user_id}")
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        reply = f"💫 Сейчас ИИ недоступен, попробуй чуть позже или свяжись с {ADMIN_CONTACT}."
    
    history.append(f"Каоруко: {reply}")
    context.user_data["history"] = history
    
    # Кнопка меню под каждым сообщением
    keyboard = [
        [InlineKeyboardButton("📱 Меню", callback_data="main_menu")],
        [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(reply, reply_markup=reply_markup)

# ==== АДМИНСКИЕ ОБРАБОТЧИКИ ====
async def handle_admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поиска пользователя"""
    target_id = update.message.text.strip()
    context.user_data['awaiting_user_id'] = False
    
    if target_id in ref_data:
        keyboard = [[InlineKeyboardButton("👤 Просмотреть", callback_data=f"viewuser_{target_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"✅ Пользователь {target_id} найден!", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ Пользователь не найден")

async def handle_admin_message_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отправки сообщения пользователю"""
    target_id = context.user_data.get('message_to_user')
    message_text = update.message.text
    
    if target_id and message_text:
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text=f"📨 Сообщение от администратора:\n\n{message_text}\n\n📞 Поддержка: {ADMIN_CONTACT}"
            )
            await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}")
            logger.info(f"Админ {update.effective_user.id} отправил сообщение пользователю {target_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")
    
    context.user_data['awaiting_message'] = False
    context.user_data['message_to_user'] = None

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка рассылки"""
    message_text = update.message.text
    context.user_data['awaiting_broadcast'] = False
    
    success = 0
    failed = 0
    
    status_msg = await update.message.reply_text("📢 Начинаю рассылку...")
    
    for uid in ref_data.keys():
        try:
            await context.bot.send_message(
                chat_id=int(uid), 
                text=f"{message_text}\n\n📞 Поддержка: {ADMIN_CONTACT}"
            )
            success += 1
        except Exception:
            failed += 1
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {success}\n"
        f"❌ Не доставлено: {failed}\n\n"
        f"📞 Контакт поддержка: {ADMIN_CONTACT}"
    )
    logger.info(f"Рассылка: успешно {success}, не доставлено {failed}")

# ==== АДМИН КОМАНДА ====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У тебя нет доступа к админ-панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats_detailed")],
        [
            InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users"),
            InlineKeyboardButton("💎 Управление подписками", callback_data="admin_subs_menu")
        ],
        [
            InlineKeyboardButton("💬 Управление лимитами", callback_data="admin_limits_menu"),
            InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices_menu")
        ],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton("⚙️ Настройки бота", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton("📈 Аналитика", callback_data="admin_analytics"),
            InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user")
        ],
        [InlineKeyboardButton("🔄 Проверить платежи", callback_data="admin_check_payments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🔐 Расширенная админ-панель:", reply_markup=reply_markup)
    logger.info(f"Админ-панель открыта пользователем {user_id}")

# ==== ОБРАБОТКА КНОПОК ====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    logger.info(f"Нажата кнопка: {data} пользователем {user_id}")
    
    try:
        # ==== ГЛАВНОЕ МЕНЮ ====
        if data == "main_menu":
            await show_main_menu(query, user_id)
        
        # ==== НАЧАЛО ЧАТА ====
        elif data == "start_chat":
            context.user_data["chat_mode"] = True
            context.user_data["history"] = []
            
            text = """╭━━━━━━━━━━━━━━━━━━━╮
   💬 Чат с Каоруко 🌸
╰━━━━━━━━━━━━━━━━━━━╯

Привет! Я готова пообщаться с тобой! 💖

Просто напиши мне что-нибудь, и я отвечу!

Используй кнопку "Меню" под сообщениями для навигации ✨"""
            
            keyboard = [
                [InlineKeyboardButton("📱 Главное меню", callback_data="main_menu")],
                [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # ==== ПРОФИЛЬ ====
        elif data == "menu_profile":
            if user_id not in ref_data:
                ref_data[user_id] = {
                    "limit": START_LIMIT,
                    "invites": 0,
                    "subscription_active": False,
                    "subscription_end": None
                }
                save_ref_data(ref_data)
            
            udata = ref_data[user_id]
            has_sub = check_subscription(user_id)
            
            text = f"""╭━━━━━━━━━━━━━━━━━━━╮
      👤 Твой профиль
╰━━━━━━━━━━━━━━━━━━━╯

🆔 ID: {user_id}
👤 Имя: {query.from_user.first_name}

📊 Статистика:
"""
            
            if has_sub:
                text += "✅ Подписка: Активна\n💬 Безлимитное общение\n"
                if udata.get("subscription_end"):
                    try:
                        end_date = datetime.fromisoformat(udata["subscription_end"])
                        text += f"⏰ Действует до: {end_date.strftime('%d.%m.%Y')}\n"
                    except (ValueError, TypeError):
                        pass
            else:
                text += f"💬 Сообщений: {udata.get('limit', 0)}\n"
            
            text += f"🎁 Приглашено друзей: {udata.get('invites', 0)}\n\n"
            text += f"📞 Техподдержка: {ADMIN_CONTACT}"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")],
                [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # ==== ПОДПИСКА ====
        elif data == "menu_subscribe":
            has_sub = check_subscription(user_id)
            
            text = f"""╭━━━━━━━━━━━━━━━━━━━╮
        💎 Подписка
╰━━━━━━━━━━━━━━━━━━━╯

"""
            
            if has_sub:
                sub_end = ref_data[user_id].get("subscription_end")
                if sub_end:
                    try:
                        end_date = datetime.fromisoformat(sub_end)
                        text += f"✅ Подписка активна до {end_date.strftime('%d.%m.%Y')}\n\n"
                    except (ValueError, TypeError):
                        pass
                text += "Ты можешь продлить подписку:\n\n"
            else:
                text += "🌸 Безлимитное общение с Каоруко!\n\n"
            
            month_price = SUBSCRIPTION_PRICES['month']['price']
            year_price = SUBSCRIPTION_PRICES['year']['price']
            
            text += f"📅 Месяц - ${month_price}\n"
            text += f"📆 Год - ${year_price} (выгодно!)\n\n"
            text += "💳 Оплата через CryptoBot (USDT)\n\n"
            text += f"📞 Вопросы по оплате: {ADMIN_CONTACT}"
            
            keyboard = [
                [InlineKeyboardButton(f"📅 Месяц - ${month_price}", callback_data="sub_month")],
                [InlineKeyboardButton(f"📆 Год - ${year_price}", callback_data="sub_year")],
                [InlineKeyboardButton("📞 Связаться с админом", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # ==== РЕФЕРАЛЬНАЯ СИСТЕМА ====
        elif data == "menu_referral":
            bot_username = (await context.bot.get_me()).username
            udata = ref_data.get(user_id, {"invites": 0})
            
            text = f"""╭━━━━━━━━━━━━━━━━━━━╮
   🎁 Реферальная система
╰━━━━━━━━━━━━━━━━━━━╯

Пригласи друга - получи +{REF_BONUS} сообщений!

📊 Твоя статистика:
👥 Приглашено: {udata.get('invites', 0)} друзей
💬 Получено: {udata.get('invites', 0) * REF_BONUS} сообщений

🔗 Твоя реферальная ссылка:
https://t.me/{bot_username}?start={user_id}

Отправь эту ссылку друзьям! ✨

📞 Вопросы: {ADMIN_CONTACT}"""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")],
                [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # ==== ОПЛАТА ПОДПИСКИ ====
        elif data in ["sub_month", "sub_year"]:
            sub_type = data.replace("sub_", "")
            price = SUBSCRIPTION_PRICES[sub_type]["price"]
            title = SUBSCRIPTION_PRICES[sub_type]["title"]
            
            try:
                # Создание инвойса CryptoPay
                invoice = await create_crypto_invoice(
                    amount=price,
                    description=title,
                    payload=f"{user_id}_{sub_type}"
                )
                
                if invoice and invoice.get("pay_url"):
                    text = f"""💳 Оплата подписки

{title}
💰 Цена: ${price}

Нажми кнопку ниже для оплаты через CryptoBot 👇

После оплаты подписка активируется автоматически! ✨

📞 Проблемы с оплатой? Пиши: {ADMIN_CONTACT}"""
                    
                    keyboard = [
                        [InlineKeyboardButton("💳 Оплатить", url=invoice["pay_url"])],
                        [InlineKeyboardButton("📞 Поддержка", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="menu_subscribe")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text, reply_markup=reply_markup)
                    
                    logger.info(f"Создан инвойс для {user_id}: {sub_type} за ${price}")
                else:
                    raise Exception("Не удалось создать инвойс")
            
            except Exception as e:
                logger.error(f"Ошибка создания инвойса: {e}")
                
                text = f"""💳 Оплата подписки

{title}
💰 Цена: ${price}


📞Оплата с другими сервисами обратится к :
{ADMIN_CONTACT}"""
                
                keyboard = [
                    [InlineKeyboardButton("📞 Связаться", url=f"https://t.me/{ADMIN_CONTACT.replace('@', '')}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu_subscribe")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text, reply_markup=reply_markup)
        
        # ==== АДМИН ПАНЕЛЬ ====
        if query.from_user.id not in ADMIN_IDS:
            return
        
        # Детальная статистика
        if data == "admin_stats_detailed":
            total_users = len(ref_data)
            active_subs = sum(1 for uid in ref_data if check_subscription(uid))
            total_messages = sum(stats.get("messages_sent", 0) for stats in user_stats.values())
            total_subscriptions = sum(stats.get("subscriptions", 0) for stats in user_stats.values())
            
            # Статистика за последние 7 дней
            week_ago = datetime.now() - timedelta(days=7)
            recent_users = 0
            recent_messages = 0
            
            for stats in user_stats.values():
                try:
                    last_seen = datetime.strptime(stats.get("last_seen", "2000-01-01"), "%Y-%m-%d")
                    if last_seen >= week_ago:
                        recent_users += 1
                        recent_messages += stats.get("messages_sent", 0)
                except (ValueError, TypeError):
                    continue
            
            text = f"""📊 ДЕТАЛЬНАЯ СТАТИСТИКА

👥 Пользователи:
• Всего: {total_users}
• Активные подписки: {active_subs}
• Новые (7 дней): {recent_users}

💬 Активность:
• Всего сообщений: {total_messages}
• Сообщений (7 дней): {recent_messages}
• Подписок всего: {total_subscriptions}

📈 Эффективность:
• Конверсия в подписку: {round((active_subs/total_users)*100 if total_users else 0, 1)}%
• Сообщений на пользователя: {round(total_messages/total_users if total_users else 0, 1)}"""

            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Аналитика
        elif data == "admin_analytics":
            # Анализ роста пользователей
            user_growth = {}
            for stats in user_stats.values():
                join_date = stats.get("first_seen", "2000-01-01")
                if join_date in user_growth:
                    user_growth[join_date] += 1
                else:
                    user_growth[join_date] = 1
            
            # Последние 7 дней
            last_7_days = []
            for i in range(7):
                day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                last_7_days.append((day, user_growth.get(day, 0)))
            
            last_7_days.reverse()
            
            growth_text = "Последние 7 дней:\n"
            for day, count in last_7_days:
                growth_text += f"• {day}: +{count} пользователей\n"
            
            text = f"""📈 АНАЛИТИКА БОТА

📊 Рост пользователей:
{growth_text}

💡 Рекомендации:
• Мониторь активность подписок
• Следи за конверсией
• Анализируй пики активности"""

            keyboard = [
                [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats_detailed")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Поиск пользователя
        elif data == "admin_search_user":
            text = "🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ\n\nОтправь ID пользователя для поиска:"
            
            context.user_data['awaiting_user_id'] = True
            keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Проверка платежей
        elif data == "admin_check_payments":
            await query.edit_message_text("🔄 Проверяю платежи...")
            await check_payments(context)
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("✅ Проверка платежей завершена!", reply_markup=reply_markup)
        
        # Управление пользователями
        elif data == "admin_users":
            if not ref_data:
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("❌ Нет пользователей", reply_markup=reply_markup)
                return
            
            buttons = []
            sorted_users = sorted(ref_data.items())[:20]
            
            for uid, udata in sorted_users:
                has_sub = check_subscription(uid)
                sub_icon = "💎" if has_sub else "👤"
                buttons.append([InlineKeyboardButton(
                    f"{sub_icon} {uid} (лим:{udata.get('limit', 0)}, приг:{udata.get('invites', 0)})",
                    callback_data=f"viewuser_{uid}"
                )])
            
            buttons.append([InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user")])
            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text("👥 Выбери пользователя:", reply_markup=reply_markup)
        
        # Просмотр пользователя
        elif data.startswith("viewuser_"):
            target_id = data[9:]
            
            if target_id not in ref_data:
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("❌ Пользователь не найден", reply_markup=reply_markup)
                return
            
            udata = ref_data[target_id]
            has_sub = check_subscription(target_id)
            stats = user_stats.get(target_id, {})
            
            text = f"""👤 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ

🆔 ID: {target_id}
💬 Лимит сообщений: {udata.get('limit', 0)}
🎁 Приглашений: {udata.get('invites', 0)}
"""
            
            if has_sub:
                text += "✅ Подписка: Активна\n"
                if udata.get("subscription_end"):
                    try:
                        end_date = datetime.fromisoformat(udata["subscription_end"])
                        text += f"⏰ До: {end_date.strftime('%d.%m.%Y')}\n"
                    except (ValueError, TypeError):
                        pass
            else:
                text += "❌ Подписка: Неактивна\n"
            
            # Добавляем статистику
            text += f"\n📊 Статистика:\n"
            text += f"• Сообщений отправлено: {stats.get('messages_sent', 0)}\n"
            text += f"• Первый визит: {stats.get('first_seen', 'Неизвестно')}\n"
            text += f"• Последний визит: {stats.get('last_seen', 'Неизвестно')}\n"
            text += f"• Подписок: {stats.get('subscriptions', 0)}"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Лимит", callback_data=f"addlimit_{target_id}"),
                    InlineKeyboardButton("➖ Лимит", callback_data=f"remlimit_{target_id}")
                ],
                [
                    InlineKeyboardButton("💎 Подписка", callback_data=f"addsub_{target_id}"),
                    InlineKeyboardButton("🗑️ Удалить", callback_data=f"confirmdelete_{target_id}")
                ],
                [InlineKeyboardButton("📨 Написать", callback_data=f"writeuser_{target_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_users")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Написать пользователю
        elif data.startswith("writeuser_"):
            target_id = data[10:]
            context.user_data['message_to_user'] = target_id
            context.user_data['awaiting_message'] = True
            
            text = f"📨 ОТПРАВКА СООБЩЕНИЯ\n\nПользователь: {target_id}\n\nВведите текст сообщения:"
            
            keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data=f"viewuser_{target_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Добавление лимита
        elif data.startswith("addlimit_"):
            target_id = data[9:]
            if target_id in ref_data:
                ref_data[target_id]["limit"] = ref_data[target_id].get("limit", 0) + 10
                save_ref_data(ref_data)
                await query.answer("✅ Добавлено +10 сообщений")
                
                # Обновляем отображение
                keyboard = [[InlineKeyboardButton("🔙 К пользователю", callback_data=f"viewuser_{target_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"✅ Пользователю {target_id} добавлено +10 сообщений!\n\nТекущий лимит: {ref_data[target_id]['limit']}",
                    reply_markup=reply_markup
                )
        
        # Удаление лимита
        elif data.startswith("remlimit_"):
            target_id = data[9:]
            if target_id in ref_data:
                ref_data[target_id]["limit"] = max(0, ref_data[target_id].get("limit", 0) - 10)
                save_ref_data(ref_data)
                await query.answer("✅ Удалено -10 сообщений")
                
                # Обновляем отображение
                keyboard = [[InlineKeyboardButton("🔙 К пользователю", callback_data=f"viewuser_{target_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"✅ У пользователя {target_id} удалено -10 сообщений!\n\nТекущий лимит: {ref_data[target_id]['limit']}",
                    reply_markup=reply_markup
                )
        
        # Добавление подписки
        elif data.startswith("addsub_"):
            target_id = data[7:]
            
            keyboard = [
                [InlineKeyboardButton("📅 +30 дней", callback_data=f"subsub_{target_id}_30")],
                [InlineKeyboardButton("📆 +365 дней", callback_data=f"subsub_{target_id}_365")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"viewuser_{target_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"💎 Выбери период подписки для {target_id}:", reply_markup=reply_markup)
        
        # Подтверждение добавления подписки
        elif data.startswith("subsub_"):
            parts = data[7:].split("_")
            if len(parts) == 2:
                target_id, days = parts
                days = int(days)
                add_subscription(target_id, days)
                update_user_stats(target_id, "subscription")
                
                try:
                    await context.bot.send_message(
                        chat_id=int(target_id),
                        text=f"🎉 Администратор активировал тебе подписку на {days} дней!\n\n"
                             f"💬 Теперь у тебя безлимитное общение! 🌸\n\n"
                             f"📞 Поддержка: {ADMIN_CONTACT}"
                    )
                except Exception:
                    pass
                
                await query.answer(f"✅ Подписка на {days} дней добавлена!")
                
                keyboard = [[InlineKeyboardButton("🔙 К пользователю", callback_data=f"viewuser_{target_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"✅ Подписка успешно добавлена пользователю {target_id}!", reply_markup=reply_markup)
        
        # Подтверждение удаления
        elif data.startswith("confirmdelete_"):
            target_id = data[14:]
            
            text = f"⚠️ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ\n\nУдалить пользователя {target_id}?\n\nЭто действие необратимо!"
            
            keyboard = [
                [InlineKeyboardButton("❌ Да, удалить", callback_data=f"deletenow_{target_id}")],
                [InlineKeyboardButton("🔙 Отмена", callback_data=f"viewuser_{target_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Удаление пользователя
        elif data.startswith("deletenow_"):
            target_id = data[10:]
            
            if target_id in ref_data:
                del ref_data[target_id]
                save_ref_data(ref_data)
            
            if target_id in user_stats:
                del user_stats[target_id]
                save_user_stats(user_stats)
            
            await query.answer("✅ Пользователь удалён")
            
            keyboard = [[InlineKeyboardButton("🔙 К списку", callback_data="admin_users")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ Пользователь {target_id} удалён из базы", reply_markup=reply_markup)
        
        # Рассылка
        elif data == "admin_broadcast":
            text = "📢 РАССЫЛКА\n\nОтправь текст сообщения для рассылки всем пользователям:"
            
            context.user_data['awaiting_broadcast'] = True
            keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Меню управления подписками
        elif data == "admin_subs_menu":
            active_subs = sum(1 for uid in ref_data if check_subscription(uid))
            expired_subs = sum(1 for uid in ref_data if ref_data[uid].get("subscription_end") and not check_subscription(uid))
            
            text = f"""💎 УПРАВЛЕНИЕ ПОДПИСКАМИ

📊 Статистика:
• Активные: {active_subs}
• Истёкшие: {expired_subs}

Выбери действие:"""
            
            keyboard = [
                [InlineKeyboardButton("✅ Активные подписки", callback_data="admin_active_subs")],
                [InlineKeyboardButton("❌ Истёкшие подписки", callback_data="admin_expired_subs")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Активные подписки
        elif data == "admin_active_subs":
            buttons = []
            for uid, udata in ref_data.items():
                if check_subscription(uid):
                    try:
                        end_date = datetime.fromisoformat(udata["subscription_end"])
                        buttons.append([InlineKeyboardButton(
                            f"💎 {uid} (до {end_date.strftime('%d.%m')})",
                            callback_data=f"viewuser_{uid}"
                        )])
                    except (ValueError, TypeError, KeyError):
                        continue
            
            if not buttons:
                buttons.append([InlineKeyboardButton("❌ Нет активных подписок", callback_data="admin_subs_menu")])
            else:
                buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_subs_menu")])
            
            reply_markup = InlineKeyboardMarkup(buttons[:20])  # Лимит 20
            await query.edit_message_text("✅ Активные подписки:", reply_markup=reply_markup)
        
        # Меню управления лимитами
        elif data == "admin_limits_menu":
            total_limits = sum(udata.get("limit", 0) for udata in ref_data.values())
            users_with_limits = sum(1 for udata in ref_data.values() if udata.get("limit", 0) > 0)
            
            text = f"""💬 УПРАВЛЕНИЕ ЛИМИТАМИ

📊 Статистика:
• Всего лимитов: {total_limits}
• Пользователей с лимитами: {users_with_limits}

Выбери действие:"""
            
            keyboard = [
                [InlineKeyboardButton("➕ Добавить всем +10", callback_data="admin_addall_10")],
                [InlineKeyboardButton("➕ Добавить всем +50", callback_data="admin_addall_50")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Добавить всем +10
        elif data == "admin_addall_10":
            count = 0
            for uid in ref_data:
                ref_data[uid]["limit"] = ref_data[uid].get("limit", 0) + 10
                count += 1
            save_ref_data(ref_data)
            
            await query.answer(f"✅ Добавлено +10 сообщений {count} пользователям")
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_limits_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ Успешно добавлено +10 сообщений для {count} пользователей!", reply_markup=reply_markup)
        
        # Добавить всем +50
        elif data == "admin_addall_50":
            count = 0
            for uid in ref_data:
                ref_data[uid]["limit"] = ref_data[uid].get("limit", 0) + 50
                count += 1
            save_ref_data(ref_data)
            
            await query.answer(f"✅ Добавлено +50 сообщений {count} пользователям")
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_limits_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ Успешно добавлено +50 сообщений для {count} пользователей!", reply_markup=reply_markup)
        
        # Меню управления ценами
        elif data == "admin_prices_menu":
            text = f"""💰 УПРАВЛЕНИЕ ЦЕНАМИ ПОДПИСОК

Текущие цены:
📅 Месяц: ${SUBSCRIPTION_PRICES['month']['price']}
📆 Год: ${SUBSCRIPTION_PRICES['year']['price']}

Выбери подписку для изменения:"""
            
            keyboard = [
                [InlineKeyboardButton("📅 Изменить цену месяца", callback_data="change_price_month")],
                [InlineKeyboardButton("📆 Изменить цену года", callback_data="change_price_year")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)

        # Изменение цены месяца
        elif data == "change_price_month":
            context.user_data['awaiting_price'] = "month"
            text = f"💰 ИЗМЕНЕНИЕ ЦЕНЫ МЕСЯЧНОЙ ПОДПИСКИ\n\nТекущая цена: ${SUBSCRIPTION_PRICES['month']['price']}\n\nВведите новую цену (только число):"
            
            keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="admin_prices_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)

        # Изменение цены года
        elif data == "change_price_year":
            context.user_data['awaiting_price'] = "year"
            text = f"💰 ИЗМЕНЕНИЕ ЦЕНЫ ГОДОВОЙ ПОДПИСКИ\n\nТекущая цена: ${SUBSCRIPTION_PRICES['year']['price']}\n\nВведите новую цену (только число):"
            
            keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="admin_prices_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Настройки бота
        elif data == "admin_settings":
            text = f"""⚙️ НАСТРОЙКИ БОТА

📊 Текущие параметры:
💬 Стартовый лимит: {START_LIMIT}
🎁 Реферальный бонус: {REF_BONUS}
📝 История сообщений: {MAX_HISTORY}

💎 Цены подписок:
📅 Месяц: ${SUBSCRIPTION_PRICES['month']['price']}
📆 Год: ${SUBSCRIPTION_PRICES['year']['price']}

🔑 API ключей: {len(API_KEYS)}
👤 Админов: {len(ADMIN_IDS)}
📞 Контакт поддержки: {ADMIN_CONTACT}

⚡ Статус систем:
• База пользователей: ✅ {len(ref_data)} записей
• Статистика: ✅ {len(user_stats)} записей
• CryptoPay: {'✅ Активен' if CRYPTOBOT_TOKEN else '❌ Не настроен'}"""

            keyboard = [
                [InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices_menu")],
                [InlineKeyboardButton("🔄 Перезагрузить данные", callback_data="admin_reload_data")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Перезагрузка данных
        elif data == "admin_reload_data":
            # Убираем global и просто перезагружаем данные
            new_ref_data = load_ref_data()
            new_user_stats = load_user_stats()
            
            # Очищаем и обновляем глобальные переменные
            ref_data.clear()
            user_stats.clear()
            ref_data.update(new_ref_data)
            user_stats.update(new_user_stats)
            
            text = f"""🔄 ДАННЫЕ ПЕРЕЗАГРУЖЕНЫ

✅ База пользователей: {len(ref_data)} записей
✅ Статистика: {len(user_stats)} записей

Все данные успешно обновлены из файлов."""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Возврат в админ-панель
        elif data == "admin_back":
            keyboard = [
                [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats_detailed")],
                [
                    InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users"),
                    InlineKeyboardButton("💎 Управление подписками", callback_data="admin_subs_menu")
                ],
                [
                    InlineKeyboardButton("💬 Управление лимитами", callback_data="admin_limits_menu"),
                    InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices_menu")
                ],
                [
                    InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
                    InlineKeyboardButton("⚙️ Настройки бота", callback_data="admin_settings")
                ],
                [
                    InlineKeyboardButton("📈 Аналитика", callback_data="admin_analytics"),
                    InlineKeyboardButton("🔍 Поиск пользователя", callback_data="admin_search_user")
                ],
                [InlineKeyboardButton("🔄 Проверить платежи", callback_data="admin_check_payments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🔐 Расширенная админ-панель:", reply_markup=reply_markup)
    
    except Exception as e:
        logger.error(f"Ошибка в button_callback: {e}", exc_info=True)
        await query.answer("❌ Произошла ошибка!")

# ==== ПРОВЕРКА ПЛАТЕЖЕЙ ====
async def check_payments(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка платежей CryptoPay"""
    try:
        invoices = await get_paid_invoices()
        
        for invoice in invoices:
            payload = invoice.get("payload")
            invoice_id = invoice.get("invoice_id")
            
            if payload and invoice_id:
                parts = payload.split('_')
                if len(parts) == 2:
                    user_id, sub_type = parts
                    
                    if user_id in ref_data and not ref_data[user_id].get(f"invoice_{invoice_id}", False):
                        days = SUBSCRIPTION_PRICES[sub_type]["days"]
                        add_subscription(user_id, days)
                        
                        ref_data[user_id][f"invoice_{invoice_id}"] = True
                        save_ref_data(ref_data)
                        
                        # Обновляем статистику
                        update_user_stats(user_id, "subscription")
                        
                        period_text = "месяц" if sub_type == "month" else "год"
                        try:
                            await context.bot.send_message(
                                chat_id=int(user_id),
                                text=f"✅ Оплата принята!\n\n"
                                     f"🎉 Подписка на {period_text} активирована!\n"
                                     f"💬 Теперь у тебя безлимитное общение с Каоруко! 🌸\n\n"
                                     f"📞 Поддержка: {ADMIN_CONTACT}"
                            )
                        except Exception:
                            pass
                        
                        logger.info(f"Обработан платеж: {user_id} - {sub_type}")
    
    except Exception as e:
        logger.error(f"Ошибка проверки платежей: {e}")

# ==== ЗАПУСК БОТА ====
def main():
    """Простой запуск бота"""
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Обработчики
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("admin", admin_command))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🌸 Запускаю бота Каоруко Вагури...")
        print(f"🤖 Бот: @wagurikaoruka_bot")
        print("⏳ Ожидаю сообщения...")
        
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()

