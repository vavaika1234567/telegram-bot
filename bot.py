import re
import asyncio
import logging
import json
import os
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.errors import (
    ApiIdInvalidError,
    AccessTokenInvalidError,
    PhoneNumberInvalidError
)

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
API_ID = 16191322
API_HASH = 'e39a7372de11be12f437fa178882a089'
BOT_TOKEN = '7500048654:AAFLSz_pp4ZJC6O7GWIsfI4_mLRhixIMut8'
CONFIG_FILE = 'bot_config.json'

# Ключевые слова для фильтрации
KEYWORDS = [
    r'fpv', r'мавик\w*', r'дрон\w*', r'бпла', r'mavic\w*', r'коптер\w*'
]

def load_config():
    """Загружаем конфигурацию из файла"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига: {e}")
    return {
        'source_channel': 'kherson_non_drone',
        'destination_channel': 'khersonshotm',
        'admin_id': None,
        'is_active': True
    }

def save_config(config):
    """Сохраняем конфигурацию в файл"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения конфига: {e}")

def format_message(text: str) -> str:
    """Форматирование текста сообщения"""
    # Удаляем подписи и фразы
    text = re.sub(r'@kherson_non_drone\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[, ]*повідомля(є|ють) (ОВА|очевидці)\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[, ]*ймовірна (активність|атака) [^,\.]+[,\.\s]*', '', text, flags=re.IGNORECASE)
    # Преобразуем топонимы
    text = re.sub(r'У мікрорайоні Сухарне', 'Сухарка', text, flags=re.IGNORECASE)
    text = re.sub(r'У мікрорайоні\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'У районі\s+([^\-—,]+)', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'У районі\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Залізничного вокзалу', 'Залізничний вокзал', text, flags=re.IGNORECASE)
    text = re.sub(r'\bСтепанівки\b', 'Степанівка', text, flags=re.IGNORECASE)
    # Удаляем лишние тире и пробелы
    text = re.sub(r'[—–-]+', ' - ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip(' -,\n')

    # Особые шаблоны
    if "Zala" in text:
        return 'БпЛА "Zala" над Херсоном!'
    elif "Європейська" in text or "Суворова" in text:
        return 'вул. Європейська (Суворова) - дрон!'
    elif "Антонівський" in text:
        return 'Антонівський залізничний міст - FPV!'

    # Если уже есть ключевое слово
    if any(re.search(kw, text, re.IGNORECASE) for kw in KEYWORDS):
        text = text.rstrip('!.?') + '!'
        return text

    # Если нет ключевого слова
    return f"{text} - дрон!"

async def main():
    config = load_config()
    client = TelegramClient('kherson_bot_session', API_ID, API_HASH)
    
    async def start_monitoring():
        """Запуск мониторинга канала"""
        try:
            source = await client.get_entity(config['source_channel'])
            dest = await client.get_entity(config['destination_channel'])
            
            @client.on(events.NewMessage(chats=source))
            async def handler(event):
                if not config['is_active']:
                    return
                
                text = event.message.message
                if not text or not any(re.search(kw, text, re.IGNORECASE) for kw in KEYWORDS):
                    return
                
                formatted = format_message(text)
                await client.send_message(dest, formatted, parse_mode='md')
            
            logger.info(f"Мониторинг запущен: {source.title} -> {dest.title}")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга: {e}")
            return False

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        """Обработка команды /start"""
        config['admin_id'] = event.sender_id
        save_config(config)
        
        await event.reply(
            "🤖 Бот для мониторинга каналов\n\n"
            "Доступные команды:\n"
            "/source [канал] - установить канал-источник\n"
            "/dest [канал] - установить целевой канал\n"
            "/status - текущие настройки\n"
            "/on - включить мониторинг\n"
            "/off - выключить мониторинг\n"
            "/help - справка"
        )

    @client.on(events.NewMessage(pattern='/source'))
    async def set_source(event):
        """Установка канала-источника"""
        if event.sender_id != config['admin_id']:
            return await event.reply("❌ Доступ запрещен")
        
        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            return await event.reply("Укажите username канала: /source username")
        
        config['source_channel'] = args[1].strip()
        save_config(config)
        await start_monitoring()
        await event.reply(f"✅ Канал-источник установлен: {config['source_channel']}")

    @client.on(events.NewMessage(pattern='/dest'))
    async def set_destination(event):
        """Установка целевого канала"""
        if event.sender_id != config['admin_id']:
            return await event.reply("❌ Доступ запрещен")
        
        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            return await event.reply("Укажите username канала: /dest username")
        
        config['destination_channel'] = args[1].strip()
        save_config(config)
        await event.reply(f"✅ Целевой канал установлен: {config['destination_channel']}")

    @client.on(events.NewMessage(pattern='/status'))
    async def show_status(event):
        """Показать текущие настройки"""
        status = "🟢 ВКЛЮЧЕН" if config['is_active'] else "🔴 ВЫКЛЮЧЕН"
        await event.reply(
            f"⚙️ Текущие настройки:\n\n"
            f"Источник: {config['source_channel']}\n"
            f"Получатель: {config['destination_channel']}\n"
            f"Статус: {status}"
        )

    @client.on(events.NewMessage(pattern='/on'))
    async def turn_on(event):
        """Включить мониторинг"""
        if event.sender_id != config['admin_id']:
            return await event.reply("❌ Доступ запрещен")
        
        config['is_active'] = True
        save_config(config)
        await event.reply("✅ Мониторинг включен")

    @client.on(events.NewMessage(pattern='/off'))
    async def turn_off(event):
        """Выключить мониторинг"""
        if event.sender_id != config['admin_id']:
            return await event.reply("❌ Доступ запрещен")
        
        config['is_active'] = False
        save_config(config)
        await event.reply("⏹️ Мониторинг выключен")

    # Запуск бота
    await client.start(bot_token=BOT_TOKEN)
    logger.info("Бот запущен!")
    
    # Автоматический запуск мониторинга
    if config.get('is_active', True):
        await start_monitoring()
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")