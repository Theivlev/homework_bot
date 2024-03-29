import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exception import HOMEWORKSTATUS, JSON, TelegramError

load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = os.getenv('RETRY_TIME', 600)
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICT = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    """
    try:
        logger.info(
            f'Отправка сообщения: {message}'
            f'В чат: {TELEGRAM_CHAT_ID}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        raise TelegramError(
            f'Не удалось отправить сообщение в чат'
            f'Ошибка: {error} ') from None


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    logger.info(
        f'Начала запроса к сервису с '
        f'параметром: {current_timestamp}')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Ошибка при запросе к основному API'
            f'Статус: {homework_statuses.status_code}')
    try:
        return homework_statuses.json()
    except Exception:
        raise JSON('Ошибка формата json') from None


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('начала проверки ответа сервера')
    if not isinstance(response, dict):
        raise TypeError('Передан неверный тип данных')
    logger.info('В функцию передан словарь')
    if response.get('homeworks') is None:
        raise KeyError('Отсутсвует ключ homeworks')
    logger.info('Получен доступ по ключу homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Передан неверный тип данных')
    logger.info('Передан список домашних работ по ключу homeworks')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    logger.info('Начала подготовки данных')
    if len(homework) > 0:
        logger.info('Передача домашней работы')
        if isinstance(homework, list):
            info_about_homework = homework[0]
        else:
            info_about_homework = homework
        homework_name = info_about_homework.get('homework_name')
        if homework_name is None:
            raise KeyError('Ключ homework_name отсутсвует')
        homework_status = info_about_homework.get('status')
        if homework_status is None:
            raise KeyError('Ключ status отсутсвует')
        logger.info('Поиск текущего статуса домашней работы')
        if homework_status in HOMEWORK_VERDICT:
            verdict = HOMEWORK_VERDICT[homework_status]
        else:
            raise HOMEWORKSTATUS(
                f'Статус домашней работы не соотвествует '
                f'ожидаемому: {homework_status}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return 'Домашняя работа не передана'


def check_tokens():
    """Проверяет доступность переменных окруженияю.
    которые необходимы для работы программы
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Остановка программы')
        sys.exit('Отсутсвие одного или более токенов')
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.error(error)
        raise error
    while True:
        try:
            current_timestamp = int(time.time())
            replay = get_api_answer(current_timestamp)
            homework_info = check_response(replay)
            response = homework_info
            send_message(bot, parse_status(response))
            current_timestamp = replay.get('current_date')
        except HOMEWORKSTATUS as error:
            logger.error(error)
        except TelegramError as error:
            logger.error(error)
        except JSON as error:
            logger.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s [%(levelname)s] - '
            '(%(filename)s).%(funcName)s:%(lineno)d - %(message)s'
        ),
        handlers=[
            logging.FileHandler('my_logger.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
