import flask
import json
import telebot
import prettytable as pt
import pandas as pd
from telebot import types
from io import BytesIO
import conf
from Olymper import Olymp
from moderators import moderators
from moderators import tasks

WEBHOOK_URL_BASE = "https://{}:{}".format(conf.WEBHOOK_HOST, conf.WEBHOOK_PORT) # это для работы на сервере
WEBHOOK_URL_PATH = "/{}/".format(conf.TOKEN)

bot = telebot.TeleBot(conf.TOKEN, threaded=False) # это тоже для работы на сервере
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
app = flask.Flask(__name__)

ol = Olymp(bot) # подгружается класс Olimp из Olymper.py
callmessage = {} # здесь хранятся сообщения бота, которые предлагают выбор задач (чтобы потом их можно было удалить)
callnumber = {} # здесь хранится номер задачи, выбранный учатсником (чтобы его можно было передать другой функции)
adressed = []  # здесь формируется список тех, кому адресовано сообщение модератора
changer_part = None



@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == '/start' else False) # команда /start, которая предлагает кнопки модератору
def welcome(message):
    bot.send_message(message.chat.id, f"Привет, {moderators[message.chat.id]}! =)\n"
                                      "Вот все твои возможности:", reply_markup=ol.get_moder_buttons()) # кнопки подгружаются из Olymper.py


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and not ol.active
                                                  and message.text == 'Начать олимпиаду' else False) # команда начала олимпиады
def start_olymp(message):
    ol.activate() # активация олимпиады в Olymper.py
    bot.send_message(message.chat.id, 'Олимпиада началась!', reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(message.chat.id, 'Удачи!', reply_markup=ol.get_moder_buttons())


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and ol.active
                                                  and message.text == 'Завершить олимпиаду' else False) # команда завершения олимпиады
def finish_olymp(message):
    ol.deactivate() # деактивация олимпиады в Olymper.py
    bot.send_message(message.chat.id, 'Олимпиада завершилась!', reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Список ожидания' else False) # предоставление списка ожидания модератору
def send_waiting(message):
    table = pt.PrettyTable(['Имя', 'Класс', 'Задача', 'Время']) # создание класса красивой таблички, с помощью которого выводится информация
    table.align['Имя'] = 'l'
    table.align['Класс'] = 'r'
    table.align['Задача'] = 'r'
    table.align['Время'] = 'r'
    for waiter in ol.waiting_list: # подгружается информация из списка ожидания из Olymper.py
        table.add_row([waiter['name'], waiter['grade'], waiter['number'], waiter['time']])
    try:
        bot.send_message(message.chat.id, f'<pre>{table}</pre>', parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, 'Слишком много людей в списке...')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Статусы проверяющих' else False) # предоставление статуса проверяющих модератору (аналогично)
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
                                                  and message.text == 'Получить результаты' else False) # предоставление результатов модератору в Excel файле
def results(message):
    if len(ol.participants) > 0:
        table = pd.DataFrame(data=ol.participants.values())
        table_new = pd.DataFrame()
        table_new['Имя'] = table['name']
        table_new['Класс'] = table['grade']
        table_new = pd.concat((table_new,
                               pd.DataFrame(table['marks'].tolist())), axis=1)
        wt = pd.ExcelWriter('/home/pburub/mysite/results.xlsx')
        table_new.to_excel(wt, sheet_name='results', index=False)
        wt.close()
        with open('/home/pburub/mysite/results.xlsx', 'rb') as f:
            obj = BytesIO(f.read())
            obj.name = 'results.xlsx'
            bot.send_document(message.chat.id, document=obj)
    else:
        bot.send_message(message.chat.id, 'Пусто...')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Написать всем' else False) # сообщение всем от модератора
def sendall(message):
    global adressed
    adressed = [id_tutor for id_tutor in ol.tutors.keys()] + [id_part for id_part in ol.participants.keys()] # формирование списка адресатов
    bot.send_message(message.chat.id, 'Напишите, что нужно всем передать')
    bot.register_next_step_handler(message, send_message)


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'только сдающим' else False) # сообщение участникам от модератора (аналогично)
def sendpart(message):
    global adressed
    adressed = [id_part for id_part in ol.participants.keys()]
    bot.send_message(message.chat.id, 'Напишите, что нужно передать сдающим')
    bot.register_next_step_handler(message, send_message)


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                        and message.text == 'только проверяющим' else False) # сообщение проверяющим от модератора (аналогично)
def sendtutors(message):
    global adressed
    adressed = [id_tutor for id_tutor in ol.tutors.keys()]
    bot.send_message(message.chat.id, 'Напишите, что нужно передать проверяющим')
    bot.register_next_step_handler(message, send_message)


def send_message(message): # собственно отправка сообщения тем, кто в списке адресатов
    global adressed
    for reciever in adressed:
        try:
            bot.forward_message(reciever, message.chat.id, message.message_id)
        except:
            pass
    bot.send_message(message.chat.id, 'Передали! ;)')

@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Изменить информацию об участнике' else False) # Изменение информации об участнике
def change_participant(message):
    bot.send_message(message.chat.id, 'Напишите id участника')
    bot.register_next_step_handler(message, change_participant2)

def change_participant2(message):
    global changer_part
    if message.text.isnumeric() and int(message.text) in ol.participants:
        changer_part = int(message.text)
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.row(types.KeyboardButton('Имя'), types.KeyboardButton('Класс'), types.KeyboardButton('Оценка'))
        bot.send_message(message.chat.id, 'Что нужно изменить?', reply_markup=keyboard)
        bot.register_next_step_handler(message, change_participant3)
    elif message.text.isnumeric() and int(message.text) not in ol.participants:
        bot.send_message(message.chat.id, 'Такого id среди участников нет')
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_participant3(message):
    global changer_part
    if message.text == 'Имя':
        bot.send_message(message.chat.id, 'Пришли новое имя')
        bot.register_next_step_handler(message, change_participant_name)
    elif message.text == 'Класс':
        bot.send_message(message.chat.id, 'Пришли новый класс')
        bot.register_next_step_handler(message, change_participant_grade)
    elif message.text == 'Оценка':
        bot.send_message(message.chat.id, 'Оценку для какой задачи нужно изменить?')
        bot.register_next_step_handler(message, change_participant_task)
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_participant_name(message):
    global changer_part
    ol.participants[changer_part]['name'] = message.text
    bot.send_message(message.chat.id, 'Имя успешно изменено')
    ol.save_part()

def change_participant_grade(message):
    global changer_part
    if message.text.isnumeric():
        grade = int(message.text)
        ol.participants[changer_part]['grade'] = grade
        if grade < 10:
            for i in tasks['mid'].keys():
                if i not in ol.participants[changer_part]['marks']:
                    ol.participants[changer_part]['marks'][i] = 0
        else:
            for i in tasks['high'].keys():
                if i not in ol.participants[changer_part]['marks']:
                    ol.participants[changer_part]['marks'][i] = 0
        bot.send_message(message.chat.id, 'Класс успешно изменён')
        ol.save_part()
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_participant_task(message):
    global changer_part
    if message.text.isnumeric():
        changer_part = [changer_part, int(message.text)]
        bot.send_message(message.chat.id, 'Какой балл нужно выставить за эту задачу?')
        bot.register_next_step_handler(message, change_participant_task2)
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_participant_task2(message):
    global changer_part
    if message.text.strip('-').isnumeric():
        ol.participants[changer_part[0]]['marks'][changer_part[1]] = int(message.text)
        bot.send_message(message.chat.id, 'Оценка успешно изменена')
        ol.save_part()
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Добавить участника' else False) # Добавление участника
def add_participant(message):
    bot.send_message(message.chat.id, 'Пришлите через запятую id, имя и класс')
    bot.register_next_step_handler(message, add_participant2)

def add_participant2(message):
    info = message.text.split(',')
    if len(info) == 3:
        info[0] = info[0].strip(' ')
        info[1] = info[1].strip(' ')
        info[2] = info[2].strip(' ')
        if info[0].isnumeric() and info[2].isnumeric():
            part_id = int(info[0])
            part_name = info[1]
            part_grade = int(info[2])
            if part_grade < 10:
                part_tasks = {i:0 for i in tasks['mid']}
            else:
                part_tasks = {i:0 for i in tasks['high']}
            ol.participants[part_id] = {'name': part_name, 'grade': part_grade, 'marks': part_tasks, 'isready': True}
            bot.send_message(message.chat.id, 'Участник успешно добавлен')
            ol.save_part()
        else:
           bot.send_message(message.chat.id, 'Что-то пошло не так(')
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Изменить информацию о проверяющем' else False) # Изменение информации о проверяющем
def change_tutor(message):
    bot.send_message(message.chat.id, 'Напишите id проверяющего')
    bot.register_next_step_handler(message, change_tutor2)

def change_tutor2(message):
    global changer_part
    if message.text.isnumeric() and int(message.text) in ol.tutors:
        changer_part = int(message.text)
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.row(types.KeyboardButton('Имя'), types.KeyboardButton('Ссылка'), types.KeyboardButton('Задачи'))
        bot.send_message(message.chat.id, 'Что нужно изменить?', reply_markup=keyboard)
        bot.register_next_step_handler(message, change_tutor3)
    elif message.text.isnumeric() and int(message.text) not in ol.tutors:
        bot.send_message(message.chat.id, 'Такого id нет среди проверяющих')
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_tutor3(message):
    global changer_part
    if message.text == 'Имя':
        bot.send_message(message.chat.id, 'Пришли новое имя')
        bot.register_next_step_handler(message, change_tutor_name)
    elif message.text == 'Ссылка':
        bot.send_message(message.chat.id, 'Пришли новую ссылку')
        bot.register_next_step_handler(message, change_tutor_link)
    elif message.text == 'Задачи':
        bot.send_message(message.chat.id, 'Пришли список задач через запятую')
        bot.register_next_step_handler(message, change_tutor_tasks)
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def change_tutor_name(message):
    global changer_part
    ol.tutors[changer_part]['name'] = message.text
    bot.send_message(message.chat.id, 'Имя успешно изменено')
    ol.save_tutors()

def change_tutor_link(message):
    global changer_part
    ol.tutors[changer_part]['link'] = message.text
    bot.send_message(message.chat.id, 'Ссылка успешно изменена')
    ol.save_tutors()

def change_tutor_tasks(message):
    global changer_part
    if message.text.replace(' ', '').replace(',', '').isnumeric():
        tutor_tasks = list(map(int, message.text.replace(' ', '').split(',')))
        ol.tutors[changer_part]['numbers'] = tutor_tasks
        bot.send_message(message.chat.id, 'Список задач успешно изменён')
        ol.save_tutors()

@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys()
                                                  and message.text == 'Добавить проверяющего' else False) # Добавление проверяющего
def add_tutor(message):
    bot.send_message(message.chat.id, 'Пришлите через запятую id и имя')
    bot.register_next_step_handler(message, add_tutor2)

def add_tutor2(message):
    global changer_part
    info = message.text.replace(' ', '').split(',')
    if len(info) == 2 and info[0].isnumeric():
        changer_part = [int(info[0]), info[1]]
        bot.send_message(message.chat.id, 'Пришлите ссылку')
        bot.register_next_step_handler(message, add_tutor3)
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

def add_tutor3(message):
    global changer_part
    changer_part.append(message.text)
    bot.send_message(message.chat.id, 'Пришлите через запятую задачи')
    bot.register_next_step_handler(message, add_tutor4)

def add_tutor4(message):
    global changer_part
    if message.text.replace(' ', '').replace(',', '').isnumeric():
        tutor_tasks = list(map(int, message.text.replace(' ', '').split(',')))
        ol.tutors[changer_part[0]] = {'name': changer_part[1], 'link': changer_part[2], 'numbers': tutor_tasks, 'isready': False,
                                               'last': {'id': None, 'number': None}}
        bot.send_message(message.chat.id, 'Проверяющий успешно добавлен')
        ol.save_tutors()
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так(')

@bot.message_handler(func=lambda message: True if message.chat.id in ol.participants.keys() and ol.active and
                                ol.participants[message.chat.id]['isready'] == True and message.text == '/request' else False) # запрос от участников
def interface(message):
    keyboard = types.InlineKeyboardMarkup(row_width=3) # создание клавиатуры
    dct_items = ol.participants[message.chat.id]['marks'].items()
    for number, ev in sorted(dct_items, key=lambda x: x[0]): # смотрим, на доступные им задачи и оценки
        if -2 <= ev <= 0: # если оценка от -2 до 0, то эту задачу ещё можно сдать, тогда эта кнопка добавляется, иначе -- нет
            button_num = ol.conv_num(number, ol.participants[message.chat.id]['grade'])
            keyboard.add(types.InlineKeyboardButton(button_num, callback_data=number))
    global callmessage
    callmessage[message.chat.id] = bot.send_message(message.chat.id, "Какую задачу хотите сдать?",
                                                    reply_markup=keyboard).message_id # предлагаем участнику выбор, сохраняем сообщение, чтобы удалить

@bot.callback_query_handler(func=lambda call: True if call.message.chat.id in ol.participants.keys() and
                                                          int(call.data) in range(1, 14) else False) # обработка выбора
def process(call):
    global callmessage
    number = int(call.data)
    callnumber[call.message.chat.id] = number # сохраняем выбранный номер
    try:
        if callmessage[call.message.chat.id] != '':
            bot.delete_message(call.message.chat.id, callmessage[call.message.chat.id]) # удаляем сообщение с кнопками выбора
            callmessage[call.message.chat.id] = ''
    except:
        pass
    keyboard = types.ReplyKeyboardMarkup()
    yes = types.KeyboardButton('Да')
    no = types.KeyboardButton('Нет')
    keyboard.row(yes, no)
    button_num = ol.conv_num(number, ol.participants[call.message.chat.id]['grade'])
    message = bot.send_message(call.message.chat.id, f'Вы точно хотите отправить запрос сдать задачу {button_num}?',
                        reply_markup=keyboard) # уточняем, ту ли задачу имел в виду участник (с кнопками да/нет)
    bot.register_next_step_handler(message, send_request)

def send_request(message): # обработка ответа да/нет
    number = callnumber[message.chat.id] # вспоминаем номер задачи
    if message.text.lower() == 'да': # если да, то отправляем запрос
        button_num = ol.conv_num(number, ol.participants[message.chat.id]['grade'])
        bot.send_message(message.chat.id, f'Запрос сдать задачу {button_num} принят.',
                                                                            reply_markup=types.ReplyKeyboardRemove())
        ol.moder_wait() # сначала смотрим список ожидания
        ol.request(ol.participants[message.chat.id]['name'], ol.participants[message.chat.id]['grade'],
                                                                                        number, message.chat.id) # отправляем запрос в Olymper.py
    else: # иначе -- не отправляем запрос, предлагаем выбрать снова
        bot.send_message(message.chat.id, 'Чтобы сдать другую задачу, отправьте команду /request и выберите номер.',
                                    reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: True if message.chat.id in ol.participants.keys() and ol.active and
                                ol.participants[message.chat.id]['isready'] == 'SEARCH' and message.text == '/leavewaitinglist' else False) # запрос покинуть список ожидания от учатника
def leavewo(message):
    ol.leave_waiting_list(message.chat.id) # выполняем действие в Olymper.py
    bot.send_message(message.chat.id, 'Когда будете готовы сдать какую-либо задачу, напишите /request')

@bot.message_handler(func=lambda message: True if message.chat.id in ol.tutors.keys()
                                and ol.tutors[message.chat.id]['isready'] == False
                                and ol.tutors[message.chat.id]['last']['id'] == None
                                and message.text == '/free' else False) # команда выставления статуса "свободен" проверяющим
def free_tutor(message):
    ol.tutors[message.chat.id]['isready'] = True # меняю статус проверяющего
    with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f: # сохраняю в файл изменённое состояние
        json.dump(ol.tutors, f, ensure_ascii=False, indent='\t')
    bot.send_message(message.chat.id, 'Ожидайте следующего участника. Чтобы изменить статус на '
                                        '"Занят", отправьте /unfree')
    ol.moder_wait() # проверяю список ожидания
    return

@bot.message_handler(func=lambda message: True if message.chat.id in ol.tutors.keys()
                                and ol.tutors[message.chat.id]['isready'] == True
                                and ol.tutors[message.chat.id]['last']['id'] == None
                                and message.text == '/unfree' else False) # команда (самостоятельного) выставления статуса "занят" проверяющим
def unfree_tutor(message):
    ol.tutors[message.chat.id]['isready'] = False # меняю статус проверяющего
    with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f: # сохраняю в файл изменённое состояние
        json.dump(ol.tutors, f, ensure_ascii=False, indent='\t')
    bot.send_message(message.chat.id, 'Чтобы продолжить оценивать участников, напишите /free')
    return

@app.route(WEBHOOK_URL_PATH, methods=['POST']) # это тоже для работы на сервере
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)
