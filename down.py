import os
import re
import logging
import asyncio
import json
import requests
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
ADMIN_IDS = [7058479669]
DOWNLOAD_FOLDER = 'downloads'
STATS_FILE = 'bot_stats.json'
USERS_FILE = 'users.json'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===== ХРАНИЛИЩЕ ДАННЫХ =====
video_cache = {}
user_stats = {}
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
    global bot_stats, user_stats
    
    today = datetime.now().strftime('%Y-%m-%d')
    if bot_stats.get('last_reset') != today:
        bot_stats['downloads_today'] = 0
        bot_stats['last_reset'] = today
    
    bot_stats['total_downloads'] += 1
    bot_stats['downloads_today'] += 1
    
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
    keyboard = [
        [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("📖 Инструкция", callback_data="help"),
         InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        [InlineKeyboardButton("🎁 Поделиться ботом", callback_data="share")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("🗑 Очистить кэш", callback_data="admin_clear_cache")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_valid_url(url):
    patterns = [
        r'(https?://)?(www\.)?(instagram\.com|instagr\.am)/',
        r'(https?://)?(www\.)?(tiktok\.com|vt\.tiktok\.com)/',
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
        r'(https?://)?(www\.)?pinterest\.(com|ru|co\.uk|fr|de|jp|kr)/',
        r'(https?://)?pin\.it/',
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def get_platform(url):
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
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def get_ydl_opts(platform):
    """Улучшенные настройки yt-dlp для VPS"""
    base_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': False,
        'ignoreerrors': True,
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        'nocheckcertificate': True,
        'extract_flat': False,
        'concurrent_fragment_downloads': 10,
        'http_chunk_size': 10485760,
        'continuedl': True,
    }
    
    # Общие заголовки
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    if platform == 'YouTube':
        base_opts.update({
            'format': 'best[height<=720][filesize<50M]/best[height<=480]/best',
            'merge_output_format': 'mp4',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webpage']
                }
            },
            'http_headers': headers,
        })
    elif platform == 'TikTok':
        base_opts.update({
            'format': 'best[height<=720]',
            'merge_output_format': 'mp4',
            'extractor_args': {
                'tiktok': {
                    'app_version': '29.8.5',
                    'manifest_app_version': '29.8.5'
                }
            },
            'http_headers': {
                **headers,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
            }
        })
    elif platform == 'Instagram':
        base_opts.update({
            'format': 'best',
            'extractor_args': {
                'instagram': {
                    'extract_location': 'web'
                }
            },
            'http_headers': {
                **headers,
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Referer': 'https://www.instagram.com/',
                'X-IG-App-ID': '936619743392459',
            }
        })
    else:  # Pinterest и другие
        base_opts.update({
            'format': 'best',
            'http_headers': headers,
        })
    
    return base_opts

# ===== АЛЬТЕРНАТИВНЫЕ API =====
async def download_via_external_api(url, platform):
    """Использование внешних API как запасной вариант"""
    try:
        if platform == 'TikTok':
            # Попробуем несколько API для TikTok
            apis = [
                f"https://www.tikwm.com/api/?url={url}",
                f"https://api.tiklydown.com/api/download?url={url}",
                f"https://tikdown.org/api?url={url}",
            ]
            
            for api_url in apis:
                try:
                    response = requests.get(api_url, timeout=15)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data', {}).get('play'):
                            video_url = data['data']['play']
                            # Скачиваем видео
                            video_response = requests.get(video_url, timeout=30)
                            if video_response.status_code == 200:
                                filename = os.path.join(DOWNLOAD_FOLDER, f"tiktok_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4")
                                with open(filename, 'wb') as f:
                                    f.write(video_response.content)
                                return filename, {'title': data.get('data', {}).get('title', 'TikTok Video')}
                except:
                    continue
        
        elif platform == 'Instagram':
            # API для Instagram
            apis = [
                f"https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index?url={url}",
                f"https://api.instagram.com/oembed/?url={url}",
            ]
            
            for api_url in apis:
                try:
                    response = requests.get(api_url, timeout=15)
                    if response.status_code == 200:
                        data = response.json()
                        # Логика обработки Instagram API
                        # (зависит от конкретного API)
                except:
                    continue
    
    except Exception as e:
        logger.error(f"Ошибка внешнего API для {platform}: {e}")
    
    return None, None

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
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
• Instagram (посты, reels) ✓
• TikTok (видео) ✓  
• YouTube (видео, shorts) ✓
• Pinterest (изображения) ✓

<b>⚡️ Мои возможности:</b>
✓ Высокое качество (HD)
✓ Быстрая загрузка
✓ Поддержка разных форматов
✓ Автоматические повторы

<b>🚀 Как использовать:</b>
Просто отправьте мне ссылку на контент!
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
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
    
    elif data == "help":
        help_text = """
📖 <b>ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ</b>

<b>1️⃣ TikTok:</b>
• Откройте видео в приложении TikTok
• Нажмите "Поделиться" → "Копировать ссылку"
• Отправьте ссылку боту

<b>2️⃣ Instagram:</b>
• Откройте пост/reels в приложении
• Нажмите "..." → "Копировать ссылку"
• Отправьте ссылку боту

<b>3️⃣ YouTube:</b>
• Откройте видео в приложении или браузере
• Нажмите "Поделиться" → "Копировать"
• Отправьте ссылку боту

<b>⚠️ Если не работает:</b>
• Попробуйте другую ссылку
• Проверьте, не приватный ли аккаунт
• Подождите и попробуйте снова

<b>💡 Советы:</b>
• Используйте последние версии приложений
• Для Instagram лучше использовать ссылки из браузера
        """
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    elif data == "about":
        about_text = f"""
ℹ️ <b>О БОТЕ</b>

<b>Название:</b> Social Media Downloader Pro
<b>Версия:</b> 3.0 (VPS версия)
<b>Разработчик:</b> @elafril

<b>📊 Общая статистика:</b>
👥 Пользователей: <b>{format_number(bot_stats['total_users'])}</b>
📥 Загрузок: <b>{format_number(bot_stats['total_downloads'])}</b>
📅 Сегодня: <b>{bot_stats['downloads_today']}</b>

<b>🛠 Технологии:</b>
• Python 3.8+
• yt-dlp (последняя версия)
• Многопоточная загрузка
• Умные повторы при ошибках

<b>✅ Статус:</b> Работает на VPS сервере
        """
        
        await query.edit_message_text(
            about_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    elif data == "share":
        share_text = """
🎁 <b>ПРИГЛАСИТЕ ДРУЗЕЙ!</b>

Поделитесь ботом с друзьями:
👉 @YourBotUsername

<b>Или отправьте им эту ссылку:</b>
https://t.me/downloaderpro1_bot

<i>Бот работает на быстром VPS сервере!</i>
        """
        
        await query.edit_message_text(
            share_text,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    
    # АДМИН ФУНКЦИИ
    elif data == "admin_stats" and is_admin(user_id):
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
    animations = [
        f"⏳ Загружаю из {platform}",
        f"⏳ Загружаю из {platform}.",
        f"⏳ Загружаю из {platform}..",
        f"⏳ Загружаю из {platform}...",
    ]
    
    for i in range(15):
        try:
            await message.edit_text(animations[i % 4])
            await asyncio.sleep(0.25)
        except:
            break

async def download_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    animation_task = asyncio.create_task(animate_loading(status_message, platform))
    
    filename = None
    try:
        # Сначала пробуем прямое скачивание через yt-dlp
        ydl_opts = get_ydl_opts(platform)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получаем информацию
            info = ydl.extract_info(url, download=False)
            
            if not info:
                raise Exception("Не удалось получить информацию о контенте")
            
            # Скачиваем
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Ищем фактический файл
            if not os.path.exists(filename):
                base_name = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.jpeg', '.gif']:
                    test_file = base_name + ext
                    if os.path.exists(test_file):
                        filename = test_file
                        break
            
            if not os.path.exists(filename):
                # Если прямое скачивание не сработало, пробуем API
                await status_message.edit_text("🔄 Прямое соединение не удалось, пробую API...")
                filename, info = await download_via_external_api(url, platform)
                
                if not filename:
                    raise Exception("Все методы загрузки не сработали")
        
        file_size = os.path.getsize(filename)
        
        if file_size > 50 * 1024 * 1024:
            animation_task.cancel()
            await status_message.edit_text(
                f"❌ Файл слишком большой ({file_size / (1024*1024):.1f} МБ)\n"
                "Максимальный размер: 50 МБ"
            )
            if os.path.exists(filename):
                os.remove(filename)
            return
        
        animation_task.cancel()
        await status_message.edit_text(f"📤 Отправляю файл... ({file_size / (1024*1024):.1f} МБ)")
        
        is_video = filename.lower().endswith(('.mp4', '.webm', '.mkv', '.mov'))
        is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))
        
        title = info.get('title', 'Контент') if info else 'Контент'
        caption = f"✅ <b>{platform}</b>\n📁 {title[:80]}"
        
        with open(filename, 'rb') as file:
            if is_video:
                sent = await update.message.reply_video(
                    video=file,
                    caption=caption,
                    parse_mode='HTML',
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                )
                video_cache[url] = sent.video.file_id
            elif is_image:
                sent = await update.message.reply_photo(
                    photo=file,
                    caption=caption,
                    parse_mode='HTML',
                )
            else:
                sent = await update.message.reply_document(
                    document=file,
                    caption=caption,
                    parse_mode='HTML',
                )
        
        # Очистка
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {filename}: {e}")
        
        await status_message.delete()
        update_stats(user_id)
        
    except Exception as e:
        animation_task.cancel()
        logger.error(f"Ошибка загрузки {platform}: {e}")
        
        # Очистка файла
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass
        
        error_text = f"❌ <b>Ошибка при загрузке из {platform}</b>\n\n"
        
        if "IP address is blocked" in str(e) or "blocked" in str(e).lower():
            error_text += "🚫 <b>IP адрес заблокирован</b>\n\n"
            error_text += "TikTok/Instagram заблокировали IP вашего VPS.\n"
            error_text += "Решение:\n"
            error_text += "• Используйте прокси/VPN\n"
            error_text += "• Смените IP адрес VPS\n"
            error_text += "• Используйте residential прокси"
        elif "Private" in str(e) or "login" in str(e):
            error_text += "🔒 Контент из приватного аккаунта недоступен"
        elif "not available" in str(e) or "removed" in str(e):
            error_text += "🚫 Контент удален или недоступен"
        elif "Unsupported URL" in str(e):
            error_text += "🔗 Неподдерживаемая ссылка"
        elif "Sign in" in str(e) or "cookies" in str(e):
            error_text += "🔐 Требуется авторизация. Попробуйте другую ссылку"
        else:
            error_text += f"⚠️ Ошибка: {str(e)[:100]}"
        
        keyboard = [
            [InlineKeyboardButton("📖 Помощь", callback_data="help")],
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry")]
        ]
        
        await status_message.edit_text(
            error_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ===== РАССЫЛКА =====
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
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
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_content))
    
    logger.info("🚀 Бот запущен на VPS!")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == '__main__':
    main()