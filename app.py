import os
import json
import requests
import logging
import time

# библиотеки для автоматического нахождения нашего файла dotenv и его загрузки
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получение токена из переменной окружения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Пожалуйста, укажите токен бота в переменных окружения.")
URL = f"https://api.telegram.org/bot{TOKEN}/"

# Хранение состояний пользователей
user_states = {}


def get_questions():
    """
    Загружает вопросы из JSON-файла.
    Возвращает список вопросов или None, если произошла ошибка.
    """
    try:
        with open('questions.json', 'r', encoding='utf-8') as file:
            questions = json.load(file)
            return questions
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка при загрузке вопросов: {e}")
        return None


def send_message(chat_id, text, reply_markup=None):
    """
    Отправляет сообщение пользователю.
    Если передана клавиатура (reply_markup), она прикрепляется к сообщению.
    """
    url = URL + "sendMessage"
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")


def start_quiz(chat_id):
    """
    Запускает викторину для пользователя.
    Загружает вопросы и отправляет первый вопрос.
    """
    questions = get_questions()
    if questions:
        user_states[chat_id] = {'score': 0, 'current_question': 0, 'questions': questions}
        ask_question(chat_id)
    else:
        send_message(chat_id, "Игра недоступна. Пожалуйста, попробуйте позже.")


def ask_question(chat_id):
    """
    Отправляет текущий вопрос пользователю с кнопками вариантов ответа.
    """
    state = user_states[chat_id]
    question_index = state['current_question']
    questions = state['questions']

    if question_index >= len(questions):
        # Если вопросы закончились, завершаем игру
        send_message(chat_id, f"Игра окончена! 🙃\nВы ответили правильно на {state['score']} из {len(questions)} вопросов")
        del user_states[chat_id]
        return

    question_data = questions[question_index]
    question_text = question_data["question"]
    options = question_data["options"]

    # Создаём кнопки
    option_buttons = [{"text": option, "callback_data": option} for option in options]
    reply_markup = {"inline_keyboard": [option_buttons]}

    send_message(chat_id, question_text, reply_markup=json.dumps(reply_markup))


def handle_answer(chat_id, answer, callback_query_id):
    """
    Обрабатывает ответ пользователя на вопрос.
    Проверяет правильность ответа и отправляет следующий вопрос.
    """
    # Подтверждаем Telegram, что кнопка обработана
    url = URL + "answerCallbackQuery"
    params = {"callback_query_id": callback_query_id}
    try:
        requests.post(url, json=params)
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при подтверждении callback_query: {e}")

    if chat_id not in user_states:
        send_message(chat_id, "Игра окончена.\nНапишите /quiz, чтобы начать заново 😃🎮.")
        return

    state = user_states[chat_id]
    question_index = state['current_question']
    question_data = state['questions'][question_index]
    correct_answer = question_data['answer']

    # Проверяем ответ
    if answer == correct_answer:
        state['score'] += 1
        send_message(chat_id, "Правильно! 🎉 🎉 🎉")
    else:
        send_message(chat_id, f"Неправильно! 🙁\nПравильный ответ: {correct_answer}")

    # Переходим к следующему вопросу
    state['current_question'] += 1
    ask_question(chat_id)


def get_updates(offset=None):
    """
    Получает обновления от Telegram.
    Возвращает список обновлений или пустой список в случае ошибки.
    """
    url = URL + "getUpdates"
    params = {"timeout": 100, "offset": offset}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении обновлений: {e}")
        return {"result": []}


def main():
    """
    Главная функция. Обрабатывает входящие сообщения и ответы.
    """
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates.get("result", []):
            offset = update["update_id"] + 1

            if "message" in update:
                message_data = update["message"]
                chat_id = message_data["chat"]["id"]

                if message_data["date"] < time.time() - 10:
                    continue

                if "text" in message_data:
                    text = message_data["text"]

                    if text == "/start":
                        send_message(chat_id, "Привет! ✋\nОтправь /quiz ⬇️, чтобы начать викторину!")
                    elif text == "/quiz":
                        start_quiz(chat_id)

            if "callback_query" in update:
                callback = update["callback_query"]
                callback_data = callback["data"]
                chat_id = callback["from"]["id"]
                callback_query_id = callback["id"]  # ID callback-запроса
                handle_answer(chat_id, callback_data, callback_query_id)

        time.sleep(1)


if __name__ == '__main__':
    if TOKEN:
        main()
    else:
        logging.error("Укажите токен в переменных окружения.")
