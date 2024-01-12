"""
Verarbeitung von Lösungsübermittlungen über das "Solution Interface" (u.a. auch der Evaluationsbogen). Wird über uwsgi gestartet.
"""
from flask import (
    Flask,
    request,
    jsonify
)
import os
import json
import db_client.database_fcn as db
import get_passwords as get_pw

import traceback

pw_sql = get_pw.password_sql()
ip_server = get_pw.get_ip('SERVER_IP')
conn = db.connection("mysql+pymysql://relab:" + pw_sql + "@" + ip_server + ":3306/RobotikI")
basedir = os.path.abspath(os.path.dirname(__file__))
exchange_loc = os.path.abspath(os.path.join(os.path.dirname(__file__),os.path.pardir))

def valid_string(boolean):
    if boolean == True:
        return "korrekt"
    else:
        return "nicht korrekt"

blocked = False

uwsgi_app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__)) ## Pfad der Website auf dem Server

config_path = basedir + '/config/'

uwsgi_app.config["MAX_CONTENT_LENGTH"]=10000000
uwsgi_app.secret_key = os.urandom(24)

with open(config_path + 'solution5.json') as config_file:
    eval_config = json.load(config_file)


@uwsgi_app.route('/RobotikI/rest/be/SI/evaluation/', methods=['POST'])
def get_eval():
    """
    Speicherung des ausgefuellten Evaluationsbogens.
    """
    labnr_eval = 4 #Labornummer, nur fuer den Evaluationsbogen
    parse_error=False
    try:
        user =request.environ.get('REMOTE_USER')
        group, allowed, reason, trys = conn.get_group_solution(user, labnr_eval)
        labs = conn.get_labs(user)
        labs_done = 0
        for lab in range(4):
            if (conn.get_labScore(group,lab) > 0):
                labs_done = labs_done +1
        if labs_done < 2:
            return jsonify(resp="Sie müssen mindestens zwei Labore bearbeitet haben um an der Evaluation teilzunehmen.", success=False)

        if allowed:
            proof= []
            eval_data = request.get_json()
            eval_data2 = {}
            for quest in eval_data:
                str_quest = quest.replace("inlineRadio","quest")
                str_quest = str_quest.replace("inlineText", "quest")
                eval_data2[str_quest] = eval_data[quest]
            eval_data = eval_data2

            for exercise in eval_config:
                for quest in exercise["quests"]:
                    if quest["required"]:
                        try:
                            print(eval_data2["quest"+str(quest['id'])])
                        except:
                            #traceback.print_exc()
                            return jsonify(resp="Ihre Eingaben sind unvollständig.", success=False)

            while allowed:
                conn.write_success(group, labnr_eval)
                conn.write_solution(group, json.dumps(eval_data), labnr_eval)
                group, allowed, reason, trys = conn.get_group_solution(user, labnr_eval)

            # Score schreiben
            conn.write_success(group, labnr_eval)
            score = 1000
            str_score = "%.0f" % (score)
            print('score')
            print(score)
            conn.write_score(group, labnr_eval, score)
            return jsonify(resp="Vielen Dank für Ihre Teilnahme an der Evaluation. Sie erhalten " + str_score + " zusätzliche Punkte.", success=True)
        else:
            return jsonify(resp="Sie haben bereits einen Evaluationsbogen versendet.", success = False)
    except:
        traceback.print_exc()
        return jsonify(resp="Es ist ein interner Fehler aufgetreten.", success = False)
