import sqlite3

con = sqlite3.connect('olymp.db')
cur = con.cursor()

try:
    cur.execute('''
    CREATE TABLE tutors (
        tutor_id INT, 
        tutor_name TEXT, 
        link TEXT,
        PRIMARY KEY (tutor_id)
        )''')
    con.commit()
except:
    pass

try:
    cur.execute('''
    CREATE TABLE problems (
        tutor_id INT, 
        problem_num INT
        )''')
    con.commit()
except:
    pass

try:
    cur.execute('''
    CREATE TABLE participants (
        participant_id INT, 
        participant_name TEXT, 
        participant_grade INT,
        PRIMARY KEY (participant_id)
        )''')
    con.commit()
except:
    pass