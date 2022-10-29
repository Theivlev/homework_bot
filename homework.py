import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log',
                              maxBytes=50000000,
                              backupCount=5,
                              encoding='UTF-8'
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    '''Отправляет сообщение в Telegram чат, определяемый переменной окружения TELEGRAM_CHAT_ID'''
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Отрпавка сообщения: {message}' 
            f'В чат: {TELEGRAM_CHAT_ID}')
    except Exception as error:
        logger.error(
            f'Не удалось отправить сообщение в чат'
            f'Ошибка: {error} ')


def get_api_answer(current_timestamp):
    '''Делает запрос к единственному эндпоинту API-сервиса.'''
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error(
            f'Ошибка при запросе к API'
            f'Статус: {homework_statuses.status_code}')
        raise Exception(
            f'Ошибка при запросе к основному API'
            f'Статус: {homework_statuses.status_code}')
    try:
        return homework_statuses.json()
    except Exception as error:
        logger.error(
            f'Ошибка  ответа формата json'
            f'Ошибка: {error}')


def check_response(response):
    '''Проверяет ответ API на корректность.'''   
    if not isinstance(response, dict):
        raise TypeError('Должен передаваться словарь')
    logger.info(f'В функцию передан словарь')
    if response.get('homeworks') is None:
        logger.error(f'отсутствует ожидаемый ключ в ответе API')
        raise KeyError('Отсутсвует ключ homeworks')
    logger.info(f'Получен доступ по ключу homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Отсуствует список по ключу homeworks')
    logger.info(f'Передан список домашних работ по ключу homeworks')
    return response['homeworks']


def parse_status(homework):
    '''Извлекает из информации о конкретной домашней работе статус этой работы.'''
    if len(homework) > 0:
        logger.info(f'Передана домашняя работа')
        info_about_homework = homework
        homework_name = info_about_homework.get('homework_name')
        if homework_name is None:
            logger.error(f'отсутствует ожидаемый ключ')
            raise KeyError('Ключ homework_name отсутсвует')
        homework_status = info_about_homework.get('status')
        if homework_name is None:
            logger.error(f'отсутствует ожидаемый ключ')
            raise KeyError('Ключ status отсутсвует')
        logger.info(f'Поиск текущего статуса домашней работы')
        if homework_status in HOMEWORK_STATUSES:
                verdict = HOMEWORK_STATUSES[homework_status]          
        else:
            logger.error(
                    f'Обнаружен недокументированный статус домашней работы'
                    f'Статус: {homework_status}')
            raise TypeError(
                    f'Статус домашней работы не соотвествует ожидаемому'
                    f'Статус: {homework_status}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return 'Домашняя работа не передана'


def check_tokens():
    '''Проверяет доступность переменных окружения, которые необходимы для работы программы'''
    TOKENS = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in TOKENS:
            if token is None:
                logger.critical(f'Отсутствует обязательная переменная окружения: {token}')
                return False
    return True

def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time())
    replay = get_api_answer(current_timestamp)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    homework_info = check_response(replay)
    while True:
        try:
            response = homework_info
            send_message(bot, parse_status(response))
            current_timestamp = replay.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
