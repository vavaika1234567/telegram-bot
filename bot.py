import re
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import (
    ApiIdInvalidError,
    AccessTokenInvalidError,
    PhoneNumberInvalidError
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

API_ID = 16191322
API_HASH = 'e39a7372de11be12f437fa178882a089'
SOURCE_CHANNEL = 'kherson_non_drone'  # Без @
DESTINATION_CHANNEL = 'khersonshotm'  # Без @

KEYWORDS = [
    r'fpv', r'мавик\w*', r'дрон\w*', r'бпла', r'mavic\w*', r'коптер\w*'
]

def format_message(text: str) -> str:
    # Удаляем подписи и фразы
    text = re.sub(r'@kherson_non_drone\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[, ]*повідомля(є|ють) (ОВА|очевидці)\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[, ]*ймовірна (активність|атака) [^,\.]+[,\.\s]*', '', text, flags=re.IGNORECASE)
    # Преобразуем топонимы
    text = re.sub(r'У мікрорайоні Сухарне', 'Сухарка', text, flags=re.IGNORECASE)
    text = re.sub(r'У мікрорайоні\s+', '', text, flags=re.IGNORECASE)
    # "У районі ..." -> просто топоним
    text = re.sub(r'У районі\s+([^\-—,]+)', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'У районі\s+', '', text, flags=re.IGNORECASE)
    # Частный случай для вокзала
    text = re.sub(r'Залізничного вокзалу', 'Залізничний вокзал', text, flags=re.IGNORECASE)
    # Исправляем падежи для известных топонимов
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

    # Если уже есть ключевое слово (FPV, дрон, мавик и т.д.), просто добавляем "!"
    if any(re.search(kw, text, re.IGNORECASE) for kw in KEYWORDS):
        text = text.rstrip('!.?') + '!'
        return text

    # Если нет ключевого слова, добавляем " - дрон!"
    text = f"{text} - дрон!"
    return text

async def main():
    try:
        client = TelegramClient('kherson_user_session', API_ID, API_HASH)
        await client.start()
        logger.info("Бот успешно авторизован!")

        source_entity = await client.get_entity(SOURCE_CHANNEL)
        dest_entity = await client.get_entity(DESTINATION_CHANNEL)

        logger.info(f"Мониторинг канала: {source_entity.title} (id: {source_entity.id})")
        logger.info(f"Целевой канал: {dest_entity.title} (id: {dest_entity.id})")
        logger.info("Бот запущен и мониторит канал...")

        @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
        async def handler(event):
            try:
                text = event.message.message
                if not text:
                    return
                logger.info(f"Получено сообщение: {text[:50]}...")
                # Фильтруем по ключевым словам ДО очистки!
                if not any(re.search(kw, text, re.IGNORECASE) for kw in KEYWORDS):
                    logger.debug("Сообщение не содержит ключевых слов. Пропускаем.")
                    return
                formatted_text = format_message(text)
                logger.info(f"Форматированный текст: {formatted_text}")
                await client.send_message(
                    entity=DESTINATION_CHANNEL,
                    message=formatted_text,
                    parse_mode='md'
                )
                logger.info("Сообщение успешно отправлено!")
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {str(e)}", exc_info=True)

        await client.run_until_disconnected()

    except ApiIdInvalidError:
        logger.critical("Ошибка: Неверный API ID или API Hash. Проверьте данные на my.telegram.org")
    except AccessTokenInvalidError:
        logger.critical("Ошибка: Неверный токен бота. Проверьте токен в @BotFather")
    except ValueError as ve:
        if "Cannot find any entity corresponding to" in str(ve):
            logger.critical(f"Ошибка: Не могу найти канал. Проверьте имя канала: {SOURCE_CHANNEL} или {DESTINATION_CHANNEL}")
        else:
            logger.critical(f"Ошибка значения: {str(ve)}")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        logger.info("Бот остановлен")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
