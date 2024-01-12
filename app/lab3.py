from ReLab import uwsgi_app, socket
import ReLab
import gevent
import pdb
import numpy as np
import math
from gevent import monkey
monkey.patch_all()
from flask import (
    Flask,
    Response,
    request,
    jsonify,
    send_file
)
import os
import traceback
import json
import time
from datetime import datetime
import random
import copy

import testbed_communication.opcua_communication as tbc
import testbed_communication.yu_kinematics as robot

############# End of imports ####################################

# load config file containing quiz tasks
with open(ReLab.config_path + 'quiz3.json') as config_file:
    quiz_json = json.load(config_file)


### global variables
bDebugMode = False
#q_start_deg = []
q_start_rad = []
x_start_m = []
delta_x_m = []
q_target_rad = []
num_itr = 10              # number of iteration
score_per_task = 500        # how much points for solution of direct kinematic task?
subindex_quiz0 = 1          # subindex of quiz0 state (init3quiz)
idxMs_quiz1 = 1             # milestone index of quiz1 (Question 1)

# this poses where tested with movement about +200mm in y direction and all are within the range of vision
rand_q_deg = [[-8.7, -108.2, 105.2, -87.1, -90, 8.7],
          [9.1, -115.7, 107.5, -81.8, -90, -9.1],
          [28.1, -103.8, 83.5, -69.7, -90, -27],
          [35.6, -101.0, 123.1, -112.1, -90, -34.6],
          [78.1, -97.4, 120.1, -112.8, -90, -77.1],
          # 5
          [135.3, -97.3, 120.1, -112.8, -90, -90.2],
          [59, -103, 112, -161, -116, -24],
          [16, -113, 118, -180, -71.5, -90],
          [18, -80, 105, -147, -56, -62],
          [-70, -74.15, 80.54, -58.48, -110, -20],
          # 10
          [-128.72, -78.8, 74.15, -172, -90, 0],
          [-169.5, -87, 82, -263, -90, 0],
          [92, -90 - 15, 86, -180, -80, 0],
          [35, -67, 109, -223, -78, 0],
#          [0, -90, 90, -180, 90, -90],          # fast Home
          # 15
          [-17, -72, 97, -183, -58, -95],
          [32, -73, 83, -140, -79, -106]
          ]
rand_delta_x = np.array([[0, 0.2, 0],
                    [0, 0, 0.2],
                    [0, 0.1, 0.1],
                    [0, 0.1, -0.1]])
rand_delta_x = np.append(rand_delta_x, rand_delta_x * -1, axis=0)

def funktions_muster():
    if ReLab.glob['blocked']:
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        """
        put your code here
        """
        return jsonify(success=True, resp='Text')
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/toggle_debug/', methods=['POST'])
def toggle_debug3():
    """
    Debug-Modus wird an/ausgeschaltet
    """
    global bDebugMode
    print(' --- lab3: toggle_debug()')
    user = request.environ.get('REMOTE_USER')
    if not ReLab.conn.is_imes_user(user):
        return jsonify(success=False, resp="No permission to change debug mode.")
    else:
        receive_data = request.get_json()         # Nutzereingabe abfragen
        print(receive_data)
        bDebugMode = receive_data['bDebug']   # user input
        return jsonify(success=True, resp="Toggled debug mode.")

def generate_mv_param():
    """
    generate random movement parameter for path planning: start pose, deltaX_E
    """
    global q_start_rad, x_start_m, delta_x_m, q_target_rad

    # generate random start pose
    idx_rand = np.random.randint(0, len(rand_q_deg))
    ReLab.glob['q_start_deg'] = copy.deepcopy(rand_q_deg[idx_rand])
    q_start_rad = robot.deg2rad(ReLab.glob['q_start_deg'])
    x_start_m = robot.direct_kinematics(q_start_rad)[0][:3, -1]

    # find valid random movement
    bValidMovement = False  # fuehrt die zufaellige Bewegung zu einer gueltigen Pose?
    while not bValidMovement:
        # solange wiederholen, bis eine gueltige Bewegung gefunden
        idx_rand = np.random.randint(0, len(rand_delta_x))
        delta_x_m = copy.deepcopy(rand_delta_x[idx_rand])  # delta X des EE in Meter
        x_target_m = x_start_m + delta_x_m
        q_target_rad = robot.iterative_inv_kin(x_target_m, q_start_rad, num_itr)  # in rad
        bValidMovement = robot.isValidPose(q_target_rad, 'cylindric', [1, 1])
        if not bValidMovement:
            print("Zufällige Bewegung ist ungültig. Versuch mit nächster..")

    # move robot to random start pose
    while not tbc.isReady(ReLab.yu_nodes):
        time.sleep(0.1)
    tbc.sendLabNumber(ReLab.yu_nodes, 3)
    tbc.sendAxValues_deg(ReLab.yu_nodes, ReLab.glob['q_start_deg'])
    tbc.startAction(ReLab.yu_nodes)
    # send target pose towards yu (Yu does not move to that pose)
    while not tbc.isReady(ReLab.yu_nodes):
        time.sleep(0.1)
    tbc.sendLabNumber(ReLab.yu_nodes, 31)
    tbc.sendAxValues_deg(ReLab.yu_nodes, robot.rad2deg(q_target_rad))
    tbc.startAction(ReLab.yu_nodes)
    return
@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/initCI/', methods=['GET'])
def init3CI():
    print(' --- lab3: initCI()')
    """
    Erster Aufruf der Control Interface Seite
    Uebermitteln, ob imes-user angemeldet. Nur dann Debug-Button verfügbar
    """
    global bDebugMode
    bDebugMode = False  # neu initialisieren. Ansonsten kann der Modus u.U. auch noch im nächsten Slot fuer anderen User verfuegbar sein
    user = request.environ.get('REMOTE_USER')
    if not ReLab.conn.is_imes_user(user):
        return jsonify(b_imesUser=False)
    else:
        return jsonify(b_imesUser=True, bDebug=bDebugMode)

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/init/', methods=['GET'])
def init3():
    """
    Erster Aufruf der Control Interface Seite
    Zielpose für Labor 3 wird zufällig gepickt, ebenso die Richtung.
    """
    print(' --- lab3: init3()')
    try:
        os.remove(ReLab.basedir + "/exchange/Download.csv")
    except Exception as e:
        pass
    tbc.turnOnLight(ReLab.yu_nodes)
    ReLab.reinitialize_tb()     # reinitialize testbed: move Star towards Container B, then move to Home
    generate_mv_param()
    print("Startpose, kart. Delta und Loesung:")
    print(ReLab.glob['q_start_deg'])
    print(delta_x_m)
    print(robot.rad2deg(q_target_rad))
    delta_x_mm = delta_x_m *1000

    return jsonify(success=True, q_start_deg=ReLab.glob['q_start_deg'], delta_x_mm=delta_x_mm.tolist())

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/start/', methods=['POST'])
def test3():
    """
    Eine gültige Position wird angefahren ("anfahren" Button betätigt)
    """
    print(' --- lab3: test()')
    if ReLab.glob['blocked'] or (not ReLab.glob['ready']):
        return jsonify(success=False, resp="Bitte warten Sie, bis der vorherige Prozess abgeschlossen ist.")

    try:
        ReLab.glob['blocked'] = True
        try:
            os.remove(os.path.join(ReLab.basedir, 'exchange/Download.csv'))  # Falls Dateien am Ende heruntergeladen werden sollen
        except Exception as e:
            pass

        tbc.sendLabNumber(ReLab.yu_nodes, 32)     # State senden, in dem Bewegungsvorgaben moeglich sind
        glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                 # [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                 # ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                 [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                                 ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'dq1', 'dq2', 'dq3', 'dq4', 'dq5', 'dq6',
                                  'x', 'y', 'z'],
                                 ReLab.yu_nodes, 'extern')  # Messdaten aufnehmen

        tbc.startAction(ReLab.yu_nodes) # Starten der Bewegung
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        time.sleep(0.2)
        glet_recv.kill()        # kill measurement thread
        return jsonify(success=True)
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp="Ein unbekannter Fehler ist aufgetreten.")
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/send/', methods=['POST'])
def send3():
    """
    Die übermittelte Lösung wird überprüft.
    """
    print(' --- lab3: send3()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)

    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        signal = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True

        signal = request.get_json()
        q13_user_deg = signal['q_target_deg']
        q_user_rad = convert_user_input(q13_user_deg, q_start_rad)

        if bDebugMode:
            q_user_rad = copy.deepcopy(q_target_rad)
        bCorrect = accept_user_sol(q_user_rad, q_target_rad)
        if not bCorrect:
            # give user new robot pose and movement
            #generate_mv_param() # init3 wird neu getriggert, daher kein expliziter Aufruf nötig
            # # move robot to random start pose
            # tbc.sendAxValues_deg(ReLab.yu_nodes, ReLab.glob['q_start_deg'])
            # tbc.sendLabNumber(ReLab.yu_nodes, 3)
            # tbc.startAction(ReLab.yu_nodes)
            return jsonify(success=False, resp="Ihre Eingabe ist nicht korrekt. Sie erhalten neue Werte für Startpose und Bewegung. ")
        # if this code is executed, user gave the right answer:
        # write score
        ms = ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)
        idx_ms = 0
        if not ms[idx_ms]:  # Milestone zuvor noch nicht erreicht
            score = score_per_task + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
            ReLab.glob['score'][idx_ms] = score_per_task
            ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score)
            ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, idx_ms)
            print("Milestone geschrieben: " + str(ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)))
            print("Score geschrieben: " + str(ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)))
            return jsonify(success=True, resp="Sehr gut, richtige Lösung. Sie erhalten " + str(score_per_task) + " Punkte und können die geplante Bahn nun abfahren.")
        return jsonify(success=True, resp="Sehr gut, richtige Lösung. Da Sie diese Aufgabe bereits bestanden hatten, erhalten Sie keine neuen Punkte. Sie können die geplante Bahn nun abfahren.")

    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/send_quiz/', methods=['POST'])
def send3_quiz():
    """
    Die übermittelte Lösung (Quiz-Antworten) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab3: send3_quiz()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)
    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        receive_data = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        receive_data = request.get_json()         # Nutzereingabe abfragen
        bAnswer = receive_data['checked']           # read checked boxes
        bAnswerCorrect = [dictAnsw['truth'] for dictAnsw in quiz_json[receive_data['nQuestion']-1]['answers'] if 'truth' in dictAnsw]
        print("Nutzereingabe und ground truth")
        print(bAnswer)
        print(bAnswerCorrect)
        if bDebugMode:
            bAnswer = bAnswerCorrect

        ReLab.glob["quiz"]["attempts"] = ReLab.glob["quiz"]["attempts"] + 1
        if bAnswer == bAnswerCorrect:
            # Score und Milestone in DB schreiben
            idx_ms = ReLab.glob["quiz"]["index"] + idxMs_quiz1
            print("idx Milestone: " + str(idx_ms))
            bFirstTry = False
            if not(ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)[idx_ms]):
                bFirstTry = True
                score = ReLab.calcQuizScore(ReLab.glob["quiz"]["attempts"])
                score_lab3 = score + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)    # fuer das gesamte Labor
                ReLab.glob['score'][idx_ms] = score
                print("Score: " + str(ReLab.glob['score']))
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score_lab3)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, ReLab.glob["quiz"]["index"] + idxMs_quiz1)
                print("Milestone geschrieben: " + str(ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)))
                print("Score geschrieben: " + str(ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)))
            ReLab.glob["quiz"]["done"][ReLab.glob["quiz"]["index"]] = True
            ReLab.glob["quiz"]["index"] = ReLab.glob["quiz"]["index"] + 1
            ReLab.glob["quiz"]["attempts"] = 0

            # Roboter zum nächsten Stern verfahren
            lab3_subindex = int(ReLab.glob["lab3_subindex"][ReLab.glob["quiz"]["index"] + subindex_quiz0])
            #int(111)  # = Labor 1 bonus 1
            print("lab3_subindex = " + str(lab3_subindex))
            tbc.communicate(ReLab.yu_nodes, int(0), lab3_subindex, timeout=5)
            glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                     [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                     ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                     ReLab.yu_nodes, 'extern')
            time.sleep(0.1)
            tbc.startAction(ReLab.yu_nodes) # Starten der Bewegung
            while not ReLab.glob["ready"]:
                time.sleep(0.1)
            time.sleep(0.2)
            glet_recv.kill()        # process which wrote data to csv file
            score_lab3 = ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
            if lab3_subindex < 115:     # not the last question
                if bFirstTry:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Sie erhalten entsprechend der Anzahl Ihrer Versuche " + str(score) + " Punkte.")
                else:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Da Sie die Aufgabe bereits zuvor bearbeitet hatten, erhalten Sie keine neue Punktzahl.")
            else:
                return jsonify(success=True, resp="Sie haben alle Fragen beantwortet und dieses Labor damit abgeschlossen. Der Roboter bringt den Stern zum letzten Behälter und anschließend zurück in die Startposition. Sie haben nun insgesamt " + str(score_lab3) + " Punkte in diesem Labor erzielt und können Ihren neuen Gesamtscore auf der Startseite einsehen.")
        else:
            return jsonify(success=False, resp="Ihre Lösung ist nicht korrekt. Bitte versuchen Sie es erneut.")
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/init_quiz/', methods=['POST'])
def init3quiz():
    print(' --- lab3: init3quiz()')
    """
    Erster Aufruf des Quiz-Abschnitts
    Hier wird nur der Roboter in die Initialpose verfahren
    """
    while ReLab.glob["blocked"]:
        # vorheriger Prozess noch nicht abgeschlossen
        time.sleep(0.2)
        #print("init3quiz: waiting for blocked = False")
    try:
        ReLab.glob['blocked'] = True
        # Roboter kann im gleichen State wie in Lab1 starten
        lab3_subindex = int(ReLab.glob["lab3_subindex"][subindex_quiz0 + ReLab.glob["quiz"]["index"]])
        # int(110)  # = Labor 1 bonus 1
        print("quiz_index = " + str(ReLab.glob["quiz"]["index"]))
        print("Dieser Index müsste 110 sein:")
        print("lab3_subindex = " + str(lab3_subindex))
        tbc.send_ITP(ReLab.yu_nodes, to=5)
        while not tbc.isReady(ReLab.yu_nodes):
            time.sleep(0.1)
        tbc.sendLabNumber(ReLab.yu_nodes, lab3_subindex)
        tbc.startAction(ReLab.yu_nodes)  # Starten der Bewegung: Initialisierung Labor 1 Bonusaufgaben
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        return jsonify(sucess=True)
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab3/get_quiz/', methods=['GET'])
def getQuiz3():
    """
    Diese Funktion sendet das Quiz an den Client
    """
    # Antworten des Quiz shuffeln, damit Kopieren der Loesungen von Kommilitonen erschwert wird
    if not bDebugMode:
        for i in range(len(quiz_json)):
            quiz_json[i]['answers'] = random.sample(quiz_json[i]['answers'], len(quiz_json[i]['answers']))
    return jsonify(quiz_json)


@uwsgi_app.route(ReLab.mainroute + "/rest/be/CI/lab3/download/<identify>", methods=['GET'])
def download3(identify):
    """
    Es wird versucht die Datei  /exchange/Download.csv zur senden.

    :param identify: dummy-Parameter, um caching zu verhindern (URL ändert sich)
    :return: File oder Fehlermeldung
    """
    print(' ++++++++++++ lab3.py/download() ++++++++++++++')
    if ReLab.glob['blocked']:
        return Response("Bitte warten Sie, bis der vorherige Prozess abgeschlossen ist.")
    try:
        ReLab.glob['blocked'] = True
        return send_file(ReLab.basedir + "/exchange/Download.csv", mimetype="text/csv", as_attachment=True,
                         attachment_filename="data.csv")
    except:
        #print(traceback.print_exc())
        return Response('Es existiert keine Datei zum Download.')
    finally:
        ReLab.glob['blocked'] = False


def convert_user_input(q13_user_deg, q_st_rad):
    """
    User input zu vollständigem q-Vektor zusammensetzen und in rad ausgeben. User gibt nur q1-q3 ein
    """
    # if there is a None in user input: fill array with zeros
    q13_user_deg = np.array(q13_user_deg)
    try:
        print("user input values: " + str(np.around(q13_user_deg, decimals=2)))
    except:
        pass
    if q13_user_deg.ndim > 1:
        q13_user_deg = q13_user_deg[0]
    if None in q13_user_deg:
        q13_user_deg = np.array([0.0, 0.0, 0.0])
    q13_rad = robot.deg2rad(q13_user_deg)
    q_full_rad = copy.deepcopy(q_st_rad)
    q_full_rad[0] = q13_rad[0]
    q_full_rad[1] = q13_rad[1]
    q_full_rad[2] = q13_rad[2]
    print("user input q_full: " + str(np.around(robot.deg2rad(q13_user_deg), decimals=2)))
    return q_full_rad

def accept_user_sol(q_user_rad, q_target_rad):
    """
    TODO: Funktionsbeschreibungen ergänzen
    q_user_rad: Gelenkwinkel (in rad), die der Nutzer als Lösung eingegeben hat [6x1]
    x_target_m: vorgegebene Zielposition [3x1]
    """

    print("User input q: " + str(np.around(robot.rad2deg(q_user_rad), decimals=1)))
    print("Loesung    q: " + str(np.around(robot.rad2deg(q_target_rad), decimals=1)))

    # Vergleich auf Positionsebene
    x_user_m = robot.direct_kinematics(q_user_rad)[0][:3, -1]
    x_target_m = robot.direct_kinematics(q_target_rad)[0][:3, -1]
    # print("accept_user_sol(): ")
    # print(x_user_m)
    # print(x_target_m)
    if np.allclose(x_user_m, x_target_m, atol=1e-5, rtol=1e-5):
        return True
    else:
        return False
