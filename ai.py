import os
import re
import logging
import asyncio
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = '8318139763:AAEyH7PSxOAihXeOPiSJ7JnTMd3rZar1Rqc'
ADMIN_IDS = [7058479669]  # Замените на ваш Telegram ID
DOWNLOAD_FOLDER = 'downloads'
STATS_FILE = 'bot_stats.json'
USERS_FILE = 'users.json'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== ХРАНИЛИЩЕ ДАННЫХ =====
video_cache = {}  # {url: file_id}
user_stats = {}   # {user_id: {downloads: int, last_download: str}}
bot_stats = {
    'total_downloads': 0,
    'total_users': 0,
    'downloads_today': 0,
    'last_reset': datetime.now().strftime('%Y-%m-%d')
}

# ===== ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ =====
def load_data():
    global bot_stats, user_stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                bot_stats = json.load(f)
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                user_stats = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")

def save_data():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_stats, f, ensure_ascii=False, indent=2)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def update_stats(user_id):
    """Обновление статистики"""
    global bot_stats, user_stats
    
    # Сброс дневной статистики
    today = datetime.now().strftime('%Y-%m-%d')
    if bot_stats.get('last_reset') != today:
        bot_stats['downloads_today'] = 0
        bot_stats['last_reset'] = today
    
    # Обновляем общую статистику
    bot_stats['total_downloads'] += 1
    bot_stats['downloads_today'] += 1
    
    # Обновляем статистику пользователя
    user_id_str = str(user_id)
    if user_id_str not in user_stats:
        bot_stats['total_users'] += 1
        user_stats[user_id_str] = {
            'downloads': 0,
            'first_seen': datetime.now().isoformat(),
            'last_download': None
        }
    
    user_stats[user_id_str]['downloads'] += 1
    user_stats[user_id_str]['last_download'] = datetime.now().isoformat()
    
    save_data()

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("📖 Инструкция", callback_data="help"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        [InlineKeyboardButton("🎁 Поделиться ботом", callback_data="share")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """Админ панель"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("🗑 Очистить кэш", callback_data="admin_clear_cache")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    """Кнопка отмены"""
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def is_admin(user_id):
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

def is_valid_url(url):
    """Проверка валидности URL"""
    patterns = [
        r'(https?://)?(www\.)?(instagram\.com|instagr\.am)/',
        r'(https?://)?(www\.)?(tiktok\.com|vt\.tiktok\.com)/',
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
        r'(https?://)?(www\.)?pinterest\.(com|ru|co\.uk|fr|de|jp|kr)/',
        r'(https?://)?pin\.it/',
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def get_platform(url):
    """Определение платформы"""
    if 'instagram.com' in url or 'instagr.am' in url:
        return 'Instagram'
    elif 'tiktok.com' in url or 'vt.tiktok.com' in url:
        return 'TikTok'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    elif 'pinterest' in url or 'pin.it' in url:
        return 'Pinterest'
    return 'Неизвестно'

def format_number(num):
    """Форматирование чисел"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Регистрируем нового пользователя
    if user_id not in user_stats:
        user_stats[user_id] = {
            'downloads': 0,
            'first_seen': datetime.now().isoformat(),
            'last_download': None,
            'username': user.username or 'Unknown'
        }
        bot_stats['total_users'] += 1
        save_data()
    
    welcome_text = f"""
🎬 <b>Добро пожаловать, {user.first_name}!</b>

Я профессиональный бот для скачивания контента из социальных сетей.

<b>📱 Поддерживаемые платформы:</b>
• Instagram (посты, reels, stories, IGTV)
• TikTok (видео, без водяных знаков)
• YouTube (видео, shorts, музыка)
• Pinterest (изображения, видео)

<b>⚡️ Мои возможности:</b>
✓ Мгновенная загрузка
✓ Высокое качество (HD)
✓ Без водяных знаков
✓ Поддержка приватных аккаунтов*
✓ Массовая загрузка

<b>🚀 Как использовать:</b>
Просто отправьте мне ссылку на видео или фото!

<i>*некоторые ограничения могут применяться</i>
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ панель /admin"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к админ-панели.")
        return
    
    admin_text = """
👑 <b>АДМИН-ПАНЕЛЬ</b>

Выберите действие из меню ниже:
    """
    
    await update.message.reply_text(
        admin_text,
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )

# ===== ОБРАБОТКА CALLBACK КНОПОК =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Моя статистика
    if data == "my_stats":
        user_id_str = str(user_id)
        stats = user_stats.get(user_id_str, {})
        
        first_seen = stats.get('first_seen', 'Неизвестно')
        if first_seen != 'Неизвестно':
            first_seen = datetime.fromisoformat(first_seen).strftime('%d.%m.%Y')
        
        stats_text = f"""
📊 <b>ВАША СТАТИСТИКА</b>

👤 Пользователь: {query.from_user.first_name}
🆔 ID: <code>{user_id}</code>

📥 Загрузок всего: <b>{stats.get('downloads', 0)}</b>
📅 С нами с: {first_seen}
⭐️ Ваш ранг: {'🏆 Активный пользователь' if stats.get('downloads', 0) > 50 else '📈 Начинающий'}

🎁 <i>Приглашайте друзей и получайте бонусы!</i>
        """
        
        await query.edit_message_text(
            stats_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    # Помощь
    elif data == "help":
        help_text = """
📖 <b>ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ</b>

<b>1️⃣ Instagram:</b>
• Откройте пост/reels/story
• Нажмите "Поделиться" → "Копировать ссылку"
• Отправьте ссылку боту

<b>2️⃣ TikTok:</b>
• Откройте видео
• Нажмите "Поделиться" → "Копировать ссылку"
• Отправьте ссылку боту

<b>3️⃣ YouTube:</b>
• Откройте видео
• Нажмите "Поделиться" → "Копировать"
• Отправьте ссылку боту

<b>4️⃣ Pinterest:</b>
• Откройте пин
• Копируйте ссылку из браузера
• Отправьте ссылку боту

<b>⚠️ Ограничения:</b>
• Максимальный размер: 50 МБ
• Некоторые приватные аккаунты недоступны
• Контент защищенный DRM не поддерживается

<b>💡 Совет:</b> Для лучшего качества используйте полные ссылки!
        """
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    # О боте
    elif data == "about":
        about_text = f"""
ℹ️ <b>О БОТЕ</b>

<b>Название:</b> Social Media Downloader Pro
<b>Версия:</b> 2.0
<b>Разработчик:</b> @YourUsername

<b>📊 Общая статистика:</b>
👥 Пользователей: <b>{format_number(bot_stats['total_users'])}</b>
📥 Загрузок: <b>{format_number(bot_stats['total_downloads'])}</b>
📅 Сегодня: <b>{bot_stats['downloads_today']}</b>

<b>🎯 Миссия:</b>
Сделать загрузку контента из социальных сетей простой и быстрой для каждого!

<b>💼 Связь с разработчиком:</b>
Предложения и вопросы: @YourUsername
        """
        
        await query.edit_message_text(
            about_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    # Поделиться
    elif data == "share":
        share_text = """
🎁 <b>ПРИГЛАСИТЕ ДРУЗЕЙ!</b>

Поделитесь ботом с друзьями:
👉 @YourBotUsername

<b>Или отправьте им эту ссылку:</b>
https://t.me/YourBotUsername

<i>Чем больше пользователей - тем лучше бот!</i>
        """
        
        await query.edit_message_text(
            share_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    # АДМИН ФУНКЦИИ
    elif data == "admin_stats" and is_admin(user_id):
        # Топ пользователей
        top_users = sorted(
            user_stats.items(),
            key=lambda x: x[1].get('downloads', 0),
            reverse=True
        )[:5]
        
        top_text = "\n".join([
            f"{i+1}. ID {uid}: {data.get('downloads', 0)} загрузок"
            for i, (uid, data) in enumerate(top_users)
        ])
        
        admin_stats = f"""
📊 <b>СТАТИСТИКА БОТА</b>

<b>👥 Пользователи:</b>
• Всего: {bot_stats['total_users']}
• Активных сегодня: {bot_stats['downloads_today']}

<b>📥 Загрузки:</b>
• Всего: {bot_stats['total_downloads']}
• Сегодня: {bot_stats['downloads_today']}
• В среднем на пользователя: {bot_stats['total_downloads'] // max(bot_stats['total_users'], 1)}

<b>🏆 ТОП-5 пользователей:</b>
{top_text}

<b>💾 Кэш:</b>
• Видео в кэше: {len(video_cache)}
        """
        
        await query.edit_message_text(
            admin_stats,
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    
    elif data == "admin_broadcast" and is_admin(user_id):
        await query.edit_message_text(
            "📢 <b>РАССЫЛКА</b>\n\nОтправьте текст сообщения для рассылки всем пользователям.\n\nДля отмены используйте /cancel",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        context.user_data['waiting_for_broadcast'] = True
    
    elif data == "admin_users" and is_admin(user_id):
        # Последние 10 пользователей
        recent_users = sorted(
            user_stats.items(),
            key=lambda x: x[1].get('first_seen', ''),
            reverse=True
        )[:10]
        
        users_text = "\n".join([
            f"• ID {uid}: @{data.get('username', 'Unknown')} ({data.get('downloads', 0)} загрузок)"
            for uid, data in recent_users
        ])
        
        list_text = f"""
👥 <b>ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ</b>

{users_text}

<b>Всего пользователей:</b> {len(user_stats)}
        """
        
        await query.edit_message_text(
            list_text,
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    
    elif data == "admin_clear_cache" and is_admin(user_id):
        video_cache.clear()
        await query.edit_message_text(
            "✅ Кэш успешно очищен!",
            reply_markup=get_admin_keyboard()
        )
    
    elif data == "back_to_main":
        await query.edit_message_text(
            "🏠 Главное меню",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Действие отменено.")

# ===== СКАЧИВАНИЕ КОНТЕНТА =====
async def animate_loading(message, platform):
    """Анимация загрузки"""
    animations = [
        f"⏳ Загружаю из {platform}",
        f"⏳ Загружаю из {platform}.",
        f"⏳ Загружаю из {platform}..",
        f"⏳ Загружаю из {platform}...",
    ]
    
    for i in range(12):  # 3 секунды анимации
        try:
            await message.edit_text(animations[i % 4])
            await asyncio.sleep(0.25)
        except:
            break

async def download_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачивание контента"""
    # Проверка на рассылку
    if context.user_data.get('waiting_for_broadcast'):
        if is_admin(update.effective_user.id):
            await broadcast_message(update, context)
        return
    
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    if not is_valid_url(url):
        keyboard = [[InlineKeyboardButton("📖 Инструкция", callback_data="help")]]
        await update.message.reply_text(
            "❌ <b>Неверная ссылка!</b>\n\n"
            "Пожалуйста, отправьте ссылку на контент из:\n"
            "• Instagram\n• TikTok\n• YouTube\n• Pinterest",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Проверка кэша
    if url in video_cache:
        await update.message.reply_text("⚡️ Загружаю из кэша...")
        try:
            await update.message.reply_video(video_cache[url])
            update_stats(user_id)
            return
        except:
            del video_cache[url]
    
    platform = get_platform(url)
    status_message = await update.message.reply_text(f"⏳ Загружаю из {platform}...")
    
    # Запускаем анимацию
    animation_task = asyncio.create_task(animate_loading(status_message, platform))
    
    filename = None
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'nocheckcertificate': True,
            'concurrent_fragment_downloads': 5,
            'retries': 3,
            'fragment_retries': 3,
            'http_chunk_size': 10485760,
        }
        
        if platform == 'Pinterest':
            ydl_opts.update({
                'format': 'best',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
            })
        else:
            ydl_opts.update({
                'format': 'best[filesize<50M]/worst',
                'merge_output_format': 'mp4',
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                base_name = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.jpeg']:
                    test_file = base_name + ext
                    if os.path.exists(test_file):
                        filename = test_file
                        break
            
            if not os.path.exists(filename):
                raise FileNotFoundError("Файл не найден")
            
            file_size = os.path.getsize(filename)
            
            if file_size > 50 * 1024 * 1024:
                animation_task.cancel()
                await status_message.edit_text(
                    f"❌ Файл слишком большой ({file_size / (1024*1024):.1f} МБ)\n"
                    "Максимальный размер: 50 МБ"
                )
                os.remove(filename)
                return
            
            animation_task.cancel()
            await status_message.edit_text(f"📤 Отправляю файл... ({file_size / (1024*1024):.1f} МБ)")
            
            is_video = filename.endswith(('.mp4', '.webm', '.mkv'))
            is_image = filename.endswith(('.jpg', '.jpeg', '.png', '.gif'))
            
            caption = f"✅ <b>{platform}</b>\n📁 {info.get('title', 'Контент')[:80]}"
            
            with open(filename, 'rb') as file:
                if is_video:
                    sent = await update.message.reply_video(
                        video=file,
                        caption=caption,
                        parse_mode='HTML',
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60,
                    )
                    video_cache[url] = sent.video.file_id
                elif is_image:
                    sent = await update.message.reply_photo(
                        photo=file,
                        caption=caption,
                        parse_mode='HTML',
                    )
                else:
                    await update.message.reply_document(
                        document=file,
                        caption=caption,
                        parse_mode='HTML',
                    )
            
            if os.path.exists(filename):
                os.remove(filename)
            
            await status_message.delete()
            update_stats(user_id)
            
    except Exception as e:
        animation_task.cancel()
        logger.error(f"Ошибка: {e}")
        
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass
        
        error_text = f"❌ <b>Ошибка при загрузке из {platform}</b>\n\n"
        
        if "Private" in str(e) or "login" in str(e):
            error_text += "🔒 Контент из приватного аккаунта недоступен"
        elif "not available" in str(e):
            error_text += "🚫 Контент удален или недоступен"
        else:
            error_text += "⚠️ Попробуйте другую ссылку или обновите бота"
        
        keyboard = [[InlineKeyboardButton("📖 Помощь", callback_data="help")]]
        await status_message.edit_text(
            error_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ===== РАССЫЛКА =====
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщений"""
    if not is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    context.user_data.clear()
    
    status = await update.message.reply_text("📢 Начинаю рассылку...")
    
    success = 0
    failed = 0
    
    for user_id in user_stats.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=text,
                parse_mode='HTML'
            )
            success += 1
            await asyncio.sleep(0.05)  # Защита от флуда
        except:
            failed += 1
    
    await status.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}"
    )

# ===== ЗАПУСК БОТА =====
def main():
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_content))
    
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':

    main()
