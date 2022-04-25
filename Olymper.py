import sqlite3
from telebot import types
from datetime import datetime
from datetime import timezone
from datetime import timedelta

tz = timezone(timedelta(hours=3))


class Olymp:
    def __init__(self, bot, database='/home/pburub/mysite/olymp.db'):
        self.bot = bot
        self.waiting_list = []

        con = sqlite3.connect(database)
        cur = con.cursor()

        query_tutor = '''
        SELECT tutor_name, group_concat(problem_num, ', '), link, tutors.tutor_id
        FROM tutors
            JOIN problems ON tutors.tutor_id = problems.tutor_id
        GROUP BY tutors.tutor_id'''
        cur.execute(query_tutor)
        self.tutors = {}
        for tutor in cur.fetchall():
            problems = list(map(int, tutor[1].split(', ')))
            self.tutors[list(tutor)[3]] = {'name': tutor[0], 'link': tutor[2], 'numbers': problems, 'isready': False,
                                           'last': {'id': None, 'number': None}}

        query_participant = '''
        SELECT participant_name, participant_grade, participant_id
        FROM participants'''
        cur.execute(query_participant)
        self.participants = {}
        for participant in cur.fetchall():
            if int(participant[1]) < 10:
                self.participants[participant[2]] = {'name': participant[0], 'grade': int(participant[1]),
                                                 'marks': dict((i, 0) for i in range(1, 10)), 'isready': True}
            else:
                self.participants[participant[2]] = {'name': participant[0], 'grade': int(participant[1]),
                                                 'marks': dict((i, 0) for i in range(4, 13)), 'isready': True}
        self.active = False

    def activate(self):
        self.active = True
        for part_id in self.participants.keys():
            self.bot.send_message(part_id, r'Олимпиада началась! Чтобы сдать задачу, отправьте команду /request '
                                                  r'и выберите номер.')
        for tutor_id in self.tutors.keys():
            self.bot.send_message(tutor_id, r'Олимпиада началась! Начать принимать задачи, отправьте команду /free.')

    def deactivate(self):
        self.active = False
        for part_id in self.participants.keys():
            self.bot.send_message(part_id, r'Олимпиада завершена. Вы больше не можете отправить запрос сдать задачу, '
                                           r'но мы продолжаем работать со списком ожидания. Спасибо за участие!')
        for tutor_id in self.tutors.keys():
            self.bot.send_message(tutor_id, r'Олимпиада завершена, но мы продолжаем работать со списком ожидания. '
                                            r'Если к вам больше никто не идёт, значит, поздравляем с усешным '
                                            r'проведением олимпиады!')

    def get_moder_buttons(self):
        keyboard = types.ReplyKeyboardMarkup()
        if not self.active:
            act_button = types.KeyboardButton('Начать олимпиаду')
        else:
            act_button = types.KeyboardButton('Завершить олимпиаду')
        send_button = types.KeyboardButton('Написать всем')
        send_p_button = types.KeyboardButton('только проверяющим')
        send_a_button = types.KeyboardButton('только сдающим')
        waiting_button = types.KeyboardButton('Список ожидания')
        tutors_stat_button = types.KeyboardButton('Статусы проверяющих')
        marks_button = types.KeyboardButton('Посмотреть результаты')
        keyboard.row(send_button)
        keyboard.row(send_p_button, send_a_button)
        keyboard.row(waiting_button, tutors_stat_button, marks_button)
        keyboard.row(act_button)
        return keyboard

    def eval_process(self, id_tutor):
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.row(types.KeyboardButton('Зачтено'), types.KeyboardButton('Не зачтено'))
        keyboard.row(types.KeyboardButton('Участник не пришёл'))
        message = self.bot.send_message(id_tutor, 'Оцените ответ участника:', reply_markup=keyboard)
        self.bot.register_next_step_handler(message, self.evaluate)

    def evaluate(self, message):
        if message.text in ['Зачтено', 'Не зачтено', 'Участник не пришёл']:
            id_part = self.tutors[message.chat.id]['last']['id']
            number: int = self.tutors[message.chat.id]['last']['number']
            if message.text == 'Зачтено':
                self.participants[id_part]['marks'][number] += 3
                result = f'Ответ на задачу {number} засчитан, поздравляем!'
            if message.text == 'Не зачтено':
                self.participants[id_part]['marks'][number] -= 1
                if self.participants[id_part]['marks'][number] == -1:
                    result = f'Ответ на задачу {number} не засчитан, попробуйте ещё! У вас есть еще 2 попытки'
                if self.participants[id_part]['marks'][number] == -2:
                    result = f'Ответ на задачу {number} не засчитан, попробуйте ещё! У вас есть еще 1 попытка'
                if self.participants[id_part]['marks'][number] == -3:
                    result = f'Ответ на задачу {number} не засчитан, это была последняя попытка, но ничего страшного:' \
                             f' с другими заданиями должно повезти больше!'
            if message.text == 'Участник не пришёл':
                result = 'Вы не пришли к проверяюшему'
            self.bot.send_message(message.chat.id, 'Оценка записана. Чтобы продолжить оценивать участников, '
                                                   'напишите /free', reply_markup=types.ReplyKeyboardRemove())
            self.tutors[message.chat.id]['last'] = {'id': None, 'number': None}
            self.bot.send_message(id_part, result)
            self.participants[id_part]['isready'] = True
            self.bot.send_message(id_part, 'Когда будете готовы сдать какую-либо задачу, напишите /request')
        else:
            self.bot.send_message(message.chat.id, 'Вы ввели неверное значение. Пожалуйста, нажмите на одну из кнопок')
            self.bot.register_next_step_handler(message, self.evaluate)

    def find(self, number, id_part):
        for id_tutor, tutor in self.tutors.items():
            if number in tutor['numbers'] and tutor['isready']:
                tutor['isready'] = False
                tutor['last']['id'] = id_part
                tutor['last']['number'] = number
                self.bot.send_message(id_tutor, f'К вам идёт {self.participants[id_part]["name"]} из '
                                          f'{self.participants[id_part]["grade"]} класса '
                                          f'для проверки задания {number}.')
                self.bot.send_message(id_part,
                                      f'Задачу {number} готов(а) у вас принять {tutor["name"]} по ссылке '
                                      f'{tutor["link"]}.')
                self.eval_process(id_tutor)
                return True
        return False

    def moder_wait(self):
        queue = len(self.waiting_list)
        i = 0
        while i < queue:
            waiter = self.waiting_list[i]
            is_found = self.find(waiter['number'], waiter['id'])
            if is_found:
                self.waiting_list.pop(i)
                queue -= 1
            else:
                i += 1

    def request(self, name, grade, number, id_part):
        self.participants[id_part]['isready'] = False
        is_found = self.find(number, id_part)
        if is_found:
            return True
        self.waiting_list.append({'name': name, 'grade': grade, 'number': number, 'id': id_part,
                                  'time': datetime.now(tz).strftime("%H:%M")})
        self.bot.send_message(id_part, 'К сожалению, свободных проверяющих пока что нет, ожидайте!')
        return False
