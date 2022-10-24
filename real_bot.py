import flask
import json
import telebot
import prettytable as pt
from telebot import types
import conf
from Olymper import Olymp
from moderators import moderators

WEBHOOK_URL_BASE = "https://{}:{}".format(conf.WEBHOOK_HOST, conf.WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(conf.TOKEN)

bot = telebot.TeleBot(conf.TOKEN, threaded=False)
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
app = flask.Flask(__name__)

ol = Olymp(bot)
callmessage = {}
callnumber = {}
adressed = []


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == '/start' else False)
def welcome(message):
    bot.send_message(message.chat.id, f"Привет, {moderators[message.chat.id]}! =)\n"
                                      "Вот все твои возможности:", reply_markup=ol.get_moder_buttons())


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and not ol.active
                                                  and message.text == 'Начать олимпиаду' else False)
def start_olymp(message):
    ol.activate()
    bot.send_message(message.chat.id, 'Олимпиада началась!', reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(message.chat.id, 'Удачи!', reply_markup=ol.get_moder_buttons())


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and ol.active
                                                  and message.text == 'Завершить олимпиаду' else False)
def finish_olymp(message):
    ol.deactivate()
    bot.send_message(message.chat.id, 'Олимпиада завершилась!', reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Список ожидания' else False)
def send_waiting(message):
    table = pt.PrettyTable(['Имя', 'Класс', 'Задача', 'Время'])
    table.align['Имя'] = 'l'
    table.align['Класс'] = 'r'
    table.align['Задача'] = 'r'
    table.align['Время'] = 'r'
    for waiter in ol.waiting_list:
        table.add_row([waiter['name'], waiter['grade'], waiter['number'], waiter['time']])
    bot.send_message(message.chat.id, f'<pre>{table}</pre>', parse_mode='HTML')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Статусы проверяющих' else False)
def send_tutors(message):
    table = pt.PrettyTable(['Имя', 'Статус'])
    table.align['Имя'] = 'l'
    table.align['Статус'] = 'r'
    for tutor in ol.tutors.values():
        if tutor['isready']:
            state = 'Свободен'
        else:
            state = 'Занят'
        table.add_row([tutor['name'], state])
    bot.send_message(message.chat.id, f'<pre>{table}</pre>', parse_mode='HTML')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Посмотреть результаты' else False)
def results(message):
    table = pt.PrettyTable(['Имя', 'Класс'] + [str(i) for i in range(1, 10)])
    table.align['Имя'] = 'l'
    table.align['Класс'] = 'l'
    for part in ol.participants.values():
        table.add_row([part['name'], part['grade']] + [i for i in part['marks'].values()])
    bot.send_message(message.chat.id, f'<pre>{table}</pre>', parse_mode='HTML')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Написать всем' else False)
def sendall(message):
    global adressed
    adressed = [id_tutor for id_tutor in ol.tutors.keys()] + [id_part for id_part in ol.participants.keys()]
    bot.send_message(message.chat.id, 'Напишите, что нужно всем передать')
    bot.register_next_step_handler(message, send_message)


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'только сдающим' else False)
def sendpart(message):
    global adressed
    adressed = [id_part for id_part in ol.participants.keys()]
    bot.send_message(message.chat.id, 'Напишите, что нужно передать сдающим')
    bot.register_next_step_handler(message, send_message)


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                        and message.text == 'только проверяющим' else False)
def sendtutors(message):
    global adressed
    adressed = [id_tutor for id_tutor in ol.tutors.keys()]
    bot.send_message(message.chat.id, 'Напишите, что нужно передать проверяющим')
    bot.register_next_step_handler(message, send_message)


def send_message(message):
    global adressed
    for reciever in adressed:
        bot.forward_message(reciever, message.chat.id, message.message_id)
    bot.send_message(message.chat.id, 'Передали! ;)')


@bot.message_handler(func=lambda message: True if message.chat.id in ol.participants.keys() and ol.active and
                                ol.participants[message.chat.id]['isready'] == True and message.text == '/request' else False)
def interface(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for number, ev in ol.participants[message.chat.id]['marks'].items():
        if -2 <= ev <= 0:
            keyboard.add(types.InlineKeyboardButton(str(number), callback_data=number))
    global callmessage
    callmessage[message.chat.id] = bot.send_message(message.chat.id, "Какую задачу хотите сдать?",
                                                    reply_markup=keyboard).message_id

@bot.callback_query_handler(func=lambda call: True if call.message.chat.id in ol.participants.keys() and
                                                          int(call.data) in range(1, 13) else False)
def process(call):
    global callmessage
    number = int(call.data)
    callnumber[call.message.chat.id] = number
    if callmessage[call.message.chat.id] != '':
        bot.delete_message(call.message.chat.id, callmessage[call.message.chat.id])
        callmessage[call.message.chat.id] = ''
    keyboard = types.ReplyKeyboardMarkup()
    yes = types.KeyboardButton('Да')
    no = types.KeyboardButton('Нет')
    keyboard.row(yes, no)
    message = bot.send_message(call.message.chat.id, f'Вы точно хотите отправить запрос сдать задачу {number}?',
                        reply_markup=keyboard)
    bot.register_next_step_handler(message, send_request)

def send_request(message):
    number = callnumber[message.chat.id]
    if message.text.lower() == 'да':
        bot.send_message(message.chat.id, f'Запрос сдать задачу {number} принят.',
                                    reply_markup=types.ReplyKeyboardRemove())
        ol.moder_wait()
        ol.request(ol.participants[message.chat.id]['name'], ol.participants[message.chat.id]['grade'],
                                                                                        number, message.chat.id)
    else:
        bot.send_message(message.chat.id, 'Чтобы сдать другую задачу, отправьте команду /request и выберите номер.',
                                    reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: True if message.chat.id in ol.participants.keys() and ol.active and
                                ol.participants[message.chat.id]['isready'] == 'SEARCH' and message.text == '/leavewaitinglist' else False)
def leavewo(message):
    ol.leave_waiting_list(message.chat.id)
    bot.send_message(message.chat.id, 'Когда будете готовы сдать какую-либо задачу, напишите /request')

@bot.message_handler(func=lambda message: True if message.chat.id in ol.tutors.keys()
                                and ol.tutors[message.chat.id]['isready'] == False
                                and ol.tutors[message.chat.id]['last']['id'] == None
                                and message.text == '/free' else False)
def free_tutor(message):
    ol.tutors[message.chat.id]['isready'] = True
    with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f:
        json.dump(ol.tutors, f, ensure_ascii=False, indent='\t')
    bot.send_message(message.chat.id, 'Ожидайте следующего участника. Чтобы изменить статус на '
                                        '"Занят", отправьте /unfree.')
    ol.moder_wait()
    return

@bot.message_handler(func=lambda message: True if message.chat.id in ol.tutors.keys()
                                and ol.tutors[message.chat.id]['isready'] == True
                                and ol.tutors[message.chat.id]['last']['id'] == None
                                and message.text == '/unfree' else False)
def free_tutor(message):
    ol.tutors[message.chat.id]['isready'] = False
    with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f:
        json.dump(ol.tutors, f, ensure_ascii=False, indent='\t')
    bot.send_message(message.chat.id, 'Чтобы продолжить оценивать участников, напишите /free.')
    return

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)
