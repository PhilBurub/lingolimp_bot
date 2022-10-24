import flask
import telebot
from telebot import types
import conf
from moderators import moderators
import pandas as pd
import random
import requests
import sqlite3
import numpy as np
from create_db import create_database
import os


code_symbols = [chr(i) for i in range(48, 91)] + [chr(i) for i in range(97, 123)]


def generate_codes(n):
    global code_symbols
    codes = []
    for i in range(n):
        code = ''.join(random.choices(code_symbols, k=10))
        codes.append(code)
    return codes


WEBHOOK_URL_BASE = "https://{}:{}".format(conf.WEBHOOK_HOST, conf.WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(conf.TOKEN)

bot = telebot.TeleBot(conf.TOKEN, threaded=False)
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
app = flask.Flask(__name__)

if not os.path.exists('/home/pburub/mysite/olymp.db'):
    create_database()
tutors_table = pd.DataFrame(columns=['names', 'codes'])
participants_table = pd.DataFrame(columns=['names', 'grades'])
tutors_data = {}
part_data = {}
done = []


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and message.text == '/start'
else False)
def welcome(message):
    bot.send_message(message.chat.id, "/tutors - отправить таблицу с проверяющими (одна колонка с именами, озаглавлена "
                                      "как names)\n/participants - отправить таблицу с участниками (две колонки: одна с "
                                      "именами, озаглавлена names, втоая - классы, озаглавлена grades)")


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and message.text == '/tutors'
else False)
def tutors(message):
    msg = bot.send_message(message.chat.id, "Пришлите .xlsx файл с проверяющими")
    bot.register_next_step_handler(msg, tutor_table)


def tutor_table(file):
    global tutors_table
    try:
        file_info = bot.get_file(file.document.file_id)
        file_data = requests.get(
            'https://api.telegram.org/file/bot{0}/{1}'.format(conf.TOKEN, file_info.file_path)).content
        tutors_table = pd.read_excel(file_data)
        tutors_table["codes"] = generate_codes(tutors_table.shape[0])
        tutors_message = "Имя\tКод"
        for tutor in tutors_table.values:
            tutors_message += f"\n{tutor[0]}\t`{tutor[1]}`"
        bot.send_message(file.chat.id, tutors_message, parse_mode='MarkdownV2')
    except:
        bot.send_message(file.chat.id, 'Что-то пошло не так... Попробуйте ещё раз.')


@bot.message_handler(func=lambda message: True if message.chat.id in moderators.keys() and
                                                  message.text == '/participants' else False)
def participants(message):
    msg = bot.send_message(message.chat.id, "Пришлите .xlsx файл с участниками")
    bot.register_next_step_handler(msg, part_table)


def part_table(file):
    global participants_table
    try:
        file_info = bot.get_file(file.document.file_id)
        file_data = requests.get(
            'https://api.telegram.org/file/bot{0}/{1}'.format(conf.TOKEN, file_info.file_path)).content
        participants_table = pd.read_excel(file_data)
        bot.send_message(file.chat.id, 'Принято!')
    except:
        bot.send_message(file.chat.id, 'Что-то пошло не так... Попробуйте ещё раз.')


@bot.message_handler(func=lambda message: True if message.chat.id not in moderators.keys() and
                                                  message.chat.id not in done and message.text in tutors_table[
                                                      "codes"].values else False)
def reg_tutor(message):
    global tutors_data
    tutors_data[message.chat.id] = {}
    idx = np.where(tutors_table['codes'].values == message.text)[0][0]
    tutors_data[message.chat.id]['name'] = tutors_table['names'].values[idx]
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.row(types.KeyboardButton('Да'), types.KeyboardButton('Нет'))
    msg = bot.send_message(message.chat.id, f'Вы {tutors_data[message.chat.id]["name"]}, верно?',
                           reply_markup=keyboard)
    bot.register_next_step_handler(msg, tutor2db)


def tutor2db(message):
    global tutors_data
    if message.text.lower() == 'да':
        msg = bot.send_message(message.chat.id, 'Пришлите ссылку на Вашу зум-конференцию',
                               reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, get_link)
    else:
        bot.send_message(message.chat.id, 'Кажется, Вы ошиблись кодом',
                         reply_markup=types.ReplyKeyboardRemove())


def get_link(message):
    global tutors_data
    tutors_data[message.chat.id]['link'] = message.text
    msg = bot.send_message(message.chat.id, 'Через запятую пришлите задачи, которые вы готовы принять,'
                                            'от 1 до 12 (например, "1,2,3")',
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, get_problems)


def get_problems(message):
    global tutors_data
    try:
        tutors_data[message.chat.id]['problems'] = list(map(int, message.text.split(',')))
    except:
        bot.send_message(message.chat.id, 'Неверный формат данных. Пожалуйста, введите код и пройдите регистрацию заново.')
        return
    con = sqlite3.connect('/home/pburub/mysite/olymp.db')
    cur = con.cursor()
    cur.execute('INSERT into tutors VALUES (?,?,?)', (message.chat.id, tutors_data[message.chat.id]['name'],
                                                      tutors_data[message.chat.id]['link']))
    for problem in tutors_data[message.chat.id]['problems']:
        cur.execute('INSERT into problems VALUES (?,?)', (message.chat.id, int(problem)))
    con.commit()
    con.close()
    done.append(message.chat.id)
    bot.send_message(message.chat.id, 'Вы успешно зарегистрировались!')


@bot.message_handler(func=lambda message: True if message.chat.id not in moderators.keys() and
                                            message.chat.id not in done and message.text == '/lingolimp' else False)
def reg_part(message):
    msg = bot.send_message(message.chat.id, 'Приветствуем Вас, участник олимпиады! Пожалуста, пришлите Ваши имя и '
                            'фамилию, как указано в таблице (!), то есть, в том же порядке и с теми же символами.')
    bot.register_next_step_handler(msg, part2db)


def part2db(message):
    global participants_table
    global part_data
    if message.text in participants_table['names'].values:
        idx = np.where(participants_table['names'].values == message.text)[0][0]
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.row(types.KeyboardButton('Да'), types.KeyboardButton('Нет'))
        msg = bot.send_message(message.chat.id, f'Вы {participants_table["names"].values[idx]} из '
                                                f'{participants_table["grades"].values[idx]} класса, верно?',
                               reply_markup=keyboard)
        bot.register_next_step_handler(msg, part_finish)
        part_data[message.chat.id] = {'name': participants_table["names"].values[idx],
                                      'grade': int(participants_table["grades"].values[idx])}
    else:
        bot.send_message(message.chat.id, 'Кажется, в таблице указано иначе или же Вы не зарегистрированы. '
                                          'Пожалуйста, обратитесь к организаторам. По всем вопросам пишите Кате @matyukhan')


def part_finish(message):
    if message.text.lower() == 'да':
        con = sqlite3.connect('/home/pburub/mysite/olymp.db')
        cur = con.cursor()
        cur.execute('INSERT into participants VALUES (?,?,?)', (message.chat.id, part_data[message.chat.id]['name'],
                                                                part_data[message.chat.id]['grade']))
        con.commit()
        con.close()
        done.append(message.chat.id)
        bot.send_message(message.chat.id, 'Вы успешно зарегистрировались!', reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, 'Что-то пошло не так. Пожалуйста, обратитесь к '
                                          'организаторам. По всем вопросам пишите Кате @matyukhan', reply_markup=types.ReplyKeyboardRemove())


@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)
