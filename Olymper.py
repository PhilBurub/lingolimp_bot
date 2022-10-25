import sqlite3
import os
import json
from telebot import types
from datetime import datetime
from datetime import timezone
from datetime import timedelta

tz = timezone(timedelta(hours=3))


class Olymp: # класс, в котором хранится всё-всё-всё
    def __init__(self, bot, database='/home/pburub/mysite/olymp.db'): # запуск класса, сюда передаётся бот и база данных
        self.bot = bot
        started_before = False
        con = sqlite3.connect(database) # связь с базой данных
        cur = con.cursor()

        if os.path.exists('/home/pburub/mysite/tutors.json'): # проверяем, есть ли уже файл, регистрирующий состояния проверяющих
            # если да, то берём информацию о проверяющих из него и понимаем, что это не первый запуск олимпиады (то есть, бот до этого упал)
            started_before = True
            with open('/home/pburub/mysite/tutors.json', 'r', encoding='utf-8') as f:
                content = json.load(f)
            self.tutors = {}
            for key_t, val_t in content.items():
                self.tutors[int(key_t)] = val_t
        else: # иначе -- получаем информацию о проверяющих из базы данных
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

        if os.path.exists('/home/pburub/mysite/res.json'): # проверяем, есть ли уже файл, регистрирующий результаты
            # если да, то берём информацию об учатсниках из него и понимаем, что это не первый запуск олимпиады (то есть, бот до этого упал)
            started_before = True
            with open('/home/pburub/mysite/res.json', 'r', encoding='utf-8') as f:
                content = json.load(f)
            self.participants = {}
            for key_p, val_p in content.items():
                self.participants[int(key_p)] = val_p
                marks_str = val_p['marks']
                marks = {}
                for key_m, val_m in marks_str.items():
                    marks[int(key_m)] = val_m
                self.participants[int(key_p)]['marks'] = marks
        else: # иначе -- получаем информацию об учатсниках из базы данных
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

        if os.path.exists('/home/pburub/mysite/waiting_list.json'): # проверяем, есть ли уже файл, регистрирующий состояние списка ожидания
            # если да, то берём информацию о списке ожидания из него и понимаем, что это не первый запуск олимпиады (то есть, бот до этого упал)
            started_before = True
            with open('/home/pburub/mysite/waiting_list.json', 'r', encoding='utf-8') as f:
                self.waiting_list = json.load(f)
        else: # иначе -- создаём пустой список ожидания
            self.waiting_list = []

        for tutor_id, tutor in self.tutors.items(): # смотрим на информацию о текущем участнике проверяющих, если она есть, то заново отправляем участника на сдачу
            if tutor['last']['id'] != None:
                self.eval_process(tutor_id)

        if started_before: # если олимпиада была запущена до этого, то выставляем статус, что олимпиада активна, иначе -- завершена
            self.active = True
        else:
            self.active = False

    def activate(self): # функция актиивации олимпиады
        self.active = True # смена статуса на активный
        for part_id in self.participants.keys(): # сообщение участникам
            self.bot.send_message(part_id, r'Олимпиада началась! Чтобы сдать задачу, отправьте команду /request '
                                                  r'и выберите номер.')
        for tutor_id in self.tutors.keys(): # сообщение проверяющим
            self.bot.send_message(tutor_id, r'Олимпиада началась! Начать принимать задачи, отправьте команду /free.')

    def deactivate(self): # функция деактиивации олимпиады
        self.active = False
        for part_id in self.participants.keys(): # сообщение участникам
            self.bot.send_message(part_id, r'Олимпиада завершена. Вы больше не можете отправить запрос сдать задачу, '
                                           r'но мы продолжаем работать со списком ожидания. Спасибо за участие!')
        for tutor_id in self.tutors.keys(): # сообщение проверяющим
            self.bot.send_message(tutor_id, r'Олимпиада завершена, но мы продолжаем работать со списком ожидания. '
                                            r'Если к вам больше никто не идёт, значит, поздравляем с успешным '
                                            r'проведением олимпиады!')

    def get_moder_buttons(self): # получение кнопок для модератора
        keyboard = types.ReplyKeyboardMarkup() # создание клавиатуры
        if not self.active: # если олимпиада не активирована, то добавляем кнопку начать, если активна, то завершить
            act_button = types.KeyboardButton('Начать олимпиаду')
        else:
            act_button = types.KeyboardButton('Завершить олимпиаду')
        send_button = types.KeyboardButton('Написать всем') # добавляем оставшиеся кнопки
        send_p_button = types.KeyboardButton('только проверяющим')
        send_a_button = types.KeyboardButton('только сдающим')
        waiting_button = types.KeyboardButton('Список ожидания')
        tutors_stat_button = types.KeyboardButton('Статусы проверяющих')
        marks_button = types.KeyboardButton('Посмотреть результаты')
        keyboard.row(send_button)
        keyboard.row(send_p_button, send_a_button)
        keyboard.row(waiting_button, tutors_stat_button, marks_button)
        keyboard.row(act_button)
        return keyboard # возвращаем клавиатуру со всеми кнопками

    def eval_process(self, id_tutor): # функция оценки ответа
        keyboard = types.ReplyKeyboardMarkup() # клавиатура с тремя кнопками
        keyboard.row(types.KeyboardButton('Зачтено'), types.KeyboardButton('Не зачтено'))
        keyboard.row(types.KeyboardButton('Участник не пришёл'))
        message = self.bot.send_message(id_tutor, 'Оцените ответ участника:', reply_markup=keyboard)
        self.bot.register_next_step_handler(message, self.evaluate)

    def evaluate(self, message): # обработка ответа
        if message.text in ['Зачтено', 'Не зачтено', 'Участник не пришёл']: # если была начата одна из кнопок, то оценка записывается
            id_part = self.tutors[message.chat.id]['last']['id']
            number: int = self.tutors[message.chat.id]['last']['number']
            if message.text == 'Зачтено': # если зачтено - добавляем к результату 3, формируем сообщение, что зачтено
                self.participants[id_part]['marks'][number] += 3
                result = f'Ответ на задачу {number} засчитан, поздравляем!'
            elif message.text == 'Не зачтено': # если не зачтено - отнимаем от результата 1, формируем сообщение, сколько осталось попыток в зависимости от оценки в результатах
                self.participants[id_part]['marks'][number] -= 1
                if self.participants[id_part]['marks'][number] == -1:
                    result = f'Ответ на задачу {number} не засчитан, попробуйте ещё! У вас есть еще 2 попытки'
                elif self.participants[id_part]['marks'][number] == -2:
                    result = f'Ответ на задачу {number} не засчитан, попробуйте ещё! У вас есть еще 1 попытка'
                elif self.participants[id_part]['marks'][number] == -3:
                    result = f'Ответ на задачу {number} не засчитан, это была последняя попытка, но ничего страшного:' \
                             f' с другими заданиями должно повезти больше!'
            elif message.text == 'Участник не пришёл': # если не пришёл, просто формируем сообщение, что участник не пришёл
                result = 'Вы не пришли к проверяющему'
            self.bot.send_message(message.chat.id, 'Оценка записана. Чтобы продолжить оценивать участников, '
                                                   'напишите /free', reply_markup=types.ReplyKeyboardRemove()) # сообщение проверяющему
            self.tutors[message.chat.id]['last'] = {'id': None, 'number': None} # удаляем информацию о текущем участнике
            with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f: # обновляем информацию в файле с проверяющими
                json.dump(self.tutors, f, ensure_ascii=False, indent='\t')
            self.bot.send_message(id_part, result) # отправляем участнику сообщение с результатом
            self.participants[id_part]['isready'] = True # выставляем статус на "готов"
            with open('/home/pburub/mysite/res.json', 'w', encoding='utf-8') as f: # обновляем информацию в файле с результатами
                json.dump(self.participants, f, ensure_ascii=False, indent='\t')
            self.bot.send_message(id_part, 'Когда будете готовы сдать какую-либо задачу, напишите /request') # сообщение участнику
        else:
            self.bot.send_message(message.chat.id, 'Вы ввели неверное значение. Пожалуйста, нажмите на одну из кнопок') # если кнопка нажата не была, заново просим нажать кнопку
            self.bot.register_next_step_handler(message, self.evaluate)

    def find(self, number, id_part): # функция поиска подходящего проверяющего
        for id_tutor, tutor in self.tutors.items(): # просматриваем список с проверяющими
            if number in tutor['numbers'] and tutor['isready']:
                # если статус проверяющего "Свободен" и запрошенная задача есть в списке задач, которые от решает, то отправляем участника к нему
                if self.participants[id_part]['isready'] != 'SEARCH': # если статус участника -- не "в поиске", то завершаем функцию без дальнейших действий
                    return True
                self.participants[id_part]['isready'] = False # выставляем статус участника "занят"
                tutor['isready'] = False # выставляем статус проверяющего "занят"
                tutor['last']['id'] = id_part # вносим информацию о текущем учатнике в словарь проверяющего
                tutor['last']['number'] = number
                with open('/home/pburub/mysite/tutors.json', 'w', encoding='utf-8') as f: # фиксируем в файле с проверяющими
                    json.dump(self.tutors, f, ensure_ascii=False, indent='\t')
                self.bot.send_message(id_tutor, f'К вам идёт {self.participants[id_part]["name"]} из '
                                          f'{self.participants[id_part]["grade"]} класса '
                                          f'для проверки задания {number}.') # сообщение проверяющему
                self.bot.send_message(id_part,
                                      f'Задачу {number} готов(а) у вас принять {tutor["name"]} по ссылке '
                                      f'{tutor["link"]}.') # сообщение участнику
                self.eval_process(id_tutor) # функция оценки ответа
                return True
        return False

    def moder_wait(self): # функия проверки списка ожидания
        queue = len(self.waiting_list)
        i = 0
        while i < queue:
            waiter = self.waiting_list[i] # смотрим на каждого ожидающего
            is_found = self.find(waiter['number'], waiter['id']) # функция поиска подходящего проверяющего
            if is_found: # если нашёлся, то удаляем из списка ожидания и обновляем информацию в файле со списком ожидания
                self.waiting_list.pop(i)
                queue -= 1
                with open('/home/pburub/mysite/waiting_list.json', 'w', encoding='utf-8') as f:
                    json.dump(self.waiting_list, f, ensure_ascii=False, indent='\t')
            else: # иначе -- переходим к следующему ожидающему
                i += 1

    def request(self, name, grade, number, id_part): # обработка запроса на сдачу задачи
        self.participants[id_part]['isready'] = 'SEARCH' # выставление участнику статуса поиска
        is_found = self.find(number, id_part) # функция поиска подходящего проверяющего
        if is_found: # если найден - завершаем функцию
            return True
        # иначе - добавляем участника в список ожидания
        self.waiting_list.append({'name': name, 'grade': grade, 'number': number, 'id': id_part,
                                  'time': datetime.now(tz).strftime("%H:%M")})
        self.bot.send_message(id_part, 'К сожалению, свободных проверяющих пока что нет, ожидайте! '
                                        'Чтобы выйти из списка ожидания и попробовать сдать другую задачу, '
                                        'отправьте /leavewaitinglist, '
                                        'но помните, что тогда место в очереди будет утрачено.') # сообщение участнику
        with open('/home/pburub/mysite/waiting_list.json', 'w', encoding='utf-8') as f: # обновление информации в файле со списком ожидания
            json.dump(self.waiting_list, f, ensure_ascii=False, indent='\t')
        return False

    def leave_waiting_list(self, id_part): # функция выхода из листа ожидания
        for waiter in self.waiting_list: # ищем участника в списке ожидания
            if waiter['id'] == id_part:
                self.waiting_list.remove(waiter) # удаляем его
                self.participants[id_part]['isready'] = True # выставляем статус "гото"
                with open('/home/pburub/mysite/waiting_list.json', 'w', encoding='utf-8') as f: # обновляем информацию в файле со списком ожидания
                    json.dump(self.waiting_list, f, ensure_ascii=False, indent='\t')
                break