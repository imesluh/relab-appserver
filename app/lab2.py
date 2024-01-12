from ReLab import uwsgi_app, socket
import ReLab
import gevent
import pdb
import numpy as np
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

import testbed_communication.opcua_communication as tbc
import testbed_communication.yu_kinematics as robot

# load config file containing quiz tasks
with open(ReLab.config_path + 'quiz2.json') as config_file:
    quiz_json = json.load(config_file)


### global variables
bDebugMode = False
pose = []
valid = []
score_per_task = 500       # how much points for solution of direct kinematic task?
subindex_quiz0 = 1          # subindex of quiz0 state (init2quiz)
idxMs_quiz1 = 1             # milestone index of quiz1 (Question 1)

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

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/toggle_debug/', methods=['POST'])
def toggle_debug2():
    """
    Debug-Modus wird an/ausgeschaltet
    """
    global bDebugMode
    print(' --- lab2: toggle_debug()')
    user = request.environ.get('REMOTE_USER')
    if not ReLab.conn.is_imes_user(user):
        return jsonify(success=False, resp="No permission to change debug mode.")
    else:
        receive_data = request.get_json()         # Nutzereingabe abfragen
        print(receive_data)
        bDebugMode = receive_data['bDebug']   # user input
        return jsonify(success=True, resp="Toggled debug mode.")

def generate_poses():
    """
    generate random poses
    """
    # poses_grad, bValid = robot.generatePoses(5, np.random.randint(1, 4), 'cylindric', [1, 1], 0.05)
    poses_grad, bValid = robot.generatePoses(5, np.random.randint(3, 4), 'cylindric', [1, 1], 0.05) # mindestens drei Posen im Arbeitsraum
    return poses_grad, bValid
@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/initCI/', methods=['GET'])
def init2CI():
    print(' --- lab2: initCI()')
    """
    Erster Aufruf der Control Interface Seite
    Uebermitteln, ob imes-user angemeldet. Nur dann Debug-Button verfügbar
    """
    global bDebugMode
    bDebugMode = False          # neu initialisieren. Ansonsten kann der Modus u.U. auch noch im nächsten Slot fuer anderen User verfuegbar sein
    user = request.environ.get('REMOTE_USER')
    if not ReLab.conn.is_imes_user(user):
        return jsonify(b_imesUser=False)
    else:
        return jsonify(b_imesUser=True, bDebug=bDebugMode)

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/init/', methods=['GET'])
def init2():
    """
    Erster Aufruf der Control Interface Seite
    Zielposen für Labor 2 werden zufällig generiert.
    """
    print(' --- lab2: init2()')
    try:
        os.remove(ReLab.basedir + "/exchange/Download.csv")
    except Exception as e:
        pass
    global pose, valid
    tbc.turnOnLight(ReLab.yu_nodes)
    ReLab.reinitialize_tb()     # reinitialize testbed: move Star towards Container B, then move to Home
    pose, valid = generate_poses()
    pose = np.around(pose, decimals=0)
    print("Valid und kart. Positionen:")
    print(valid)
    for pos_label in pose:
        print(np.round_(robot.direct_kinematics(pos_label*np.pi/180)[0][:3, -1] * 1000, 2))  # in Millimeter

    return jsonify(success=True, poses=pose.tolist())

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/start/', methods=['POST'])
def test2():
    """
    Eine gültige Position wird angefahren ("anfahren" Button betätigt)
    """
    print(' --- lab2: test()')
    global pose, valid

    if ReLab.glob['blocked'] or (not ReLab.glob['ready']):
        return jsonify(success=False, resp="Bitte warten Sie, bis der vorherige Prozess abgeschlossen ist.")

    try:
        ReLab.glob['blocked'] = True
        try:
            os.remove(os.path.join(ReLab.basedir, 'exchange/Download.csv'))  # Falls Dateien am Ende heruntergeladen werden sollen
        except Exception as e:
            pass
        pose_index = request.get_json()     # get index of pose from client
        print("Index der angefahren Pose: " + str(pose_index))

        # home position anfahren, EDIT: erfolgt ueber State im YU
        #tbc.send_ITP(ReLab.yu_nodes, to=5)
        # while not ReLab.glob["ready"]:
        #     time.sleep(0.1)

        tbc.sendLabNumber(ReLab.yu_nodes, ReLab.lab_number)     # State senden, in dem Bewegungsvorgaben moeglich sind
        # Zielposition anfahren
        q_deg = pose[pose_index]
        tbc.sendAxValues_deg(ReLab.yu_nodes, q_deg)
        glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                 [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                 ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                 # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                                 # ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'dq1', 'dq2', 'dq3', 'dq4', 'dq5', 'dq6',
                                 #  'x', 'y', 'z'],
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

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/send/', methods=['POST'])
def send2():
    """
    Die übermittelte Lösung wird überprüft.
    """
    print(' --- lab2: send2()')
    global pose, valid
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)

    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        signal = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True

        signal = request.get_json()
        if bDebugMode:
            signal['valid'] = valid
        if signal['valid'] == valid:
            for pos_pred, pos_label in zip(signal['pos'], pose):
                cartCoor = robot.direct_kinematics(pos_label * np.pi / 180)[0][:3, -1] * 1000  # in Millimeter
                if bDebugMode:
                    pos_pred = cartCoor
                if None in pos_pred:
                    return jsonify(success=False, resp="Mindestens eine kartesische Position ist nicht korrekt.")

                err2 = 0         # sum of squared errors
                err_tol = 2         # tolerance for cartesian error of one pose (mm)
                for coor_pred, coor_label in zip(pos_pred, cartCoor):
                    err2 = err2 + (coor_pred - coor_label) ** 2
                err = err2 ** 0.5       # error, 2-Norm
                if err > err_tol:
                    # give user new robot poses
                    pose, valid = generate_poses()
                    return jsonify(success=False, resp="Mindestens eine kartesische Position ist nicht korrekt.")
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
                return jsonify(success=True, valid=valid, resp="Sehr gut, alles richtig. Sie erhalten " + str(score_per_task) + " Punkte und können die gültigen Positionen nun anfahren.")
            return jsonify(success=True, valid=valid, resp="Sehr gut, alles richtig. Da Sie diese Aufgabe bereits bestanden hatten, erhalten Sie keine neuen Punkte. Sie können die gültigen Positionen nun anfahren.")
        else:
            pose, valid = generate_poses() # geschieht bereits in init2(). Falls init2() durch den Client getriggert wird, ist der Funktionsaufruf hier, eigentlich nicht notwendig
            return jsonify(success=False, resp="Die Positionen sind nicht korrekt dem Arbeitsraum zugeordnet. Sie erhalten neue Posen.")#, poses=pose.tolist())
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False
    ############
    # signal = request.get_json()
    # debug_mode = True
    # if debug_mode:
    #     signal['valid'] = valid
    # if signal['valid']==valid:
    #     for pos_pred, pos_label in zip(signal['pos'], pose):
    #         cartCoor = robot.direct_kinematics(pos_label*np.pi/180)[0][:3,-1]*1000 # in Millimeter
    #         if debug_mode:
    #             pos_pred = cartCoor
    #         #print('lab1lab1.accept1()')
    #         #print(cartCoor)
    #         #print(pos_pred)
    #         err = 0
    #         for coor_pred, coor_label in zip(pos_pred, cartCoor):
    #             err = err+(coor_pred-coor_label)**2
    #         err = (err)**0.5
    #         if err >2:
    #             pose, valid = generate_poses()
    #             return jsonify(success=False, resp="Mindestens eine kartesische Position ist nicht korrekt.")#, poses=pose.tolist())
    #     return jsonify(success=True, resp="Sehr gut, alles richtig. Sie erhalten 1000 Punkte und können die gültigen Positionen nun anfahren.")
    # else:
    #     pose, valid = generate_poses()
    #     return jsonify(success=False, resp="Die Positionen sind nicht korrekt dem Arbeitsraum zugeordnet.")#, poses=pose.tolist())

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/send_quiz/', methods=['POST'])
def send2_quiz():
    """
    Die übermittelte Lösung (Quiz-Antworten) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab2: send2_quiz()')
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
                score_lab2 = score + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)    # fuer das gesamte Labor
                ReLab.glob['score'][idx_ms] = score
                print("Score: " + str(ReLab.glob['score']))
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score_lab2)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, ReLab.glob["quiz"]["index"] + idxMs_quiz1)
                print("Milestone geschrieben: " + str(ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)))
                print("Score geschrieben: " + str(ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)))
            ReLab.glob["quiz"]["done"][ReLab.glob["quiz"]["index"]] = True
            ReLab.glob["quiz"]["index"] = ReLab.glob["quiz"]["index"] + 1
            ReLab.glob["quiz"]["attempts"] = 0

            # Roboter zum nächsten Stern verfahren
            lab2_subindex = int(ReLab.glob["lab2_subindex"][ReLab.glob["quiz"]["index"] + subindex_quiz0])
            #int(111)  # = Labor 1 bonus 1
            print("lab2_subindex = " + str(lab2_subindex))
            tbc.communicate(ReLab.yu_nodes, int(0), lab2_subindex, timeout=5)
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
            score_lab2 = ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
            if lab2_subindex < 115:     # not the last question
                if bFirstTry:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Sie erhalten entsprechend der Anzahl Ihrer Versuche " + str(score) + " Punkte.")
                else:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Da Sie die Aufgabe bereits zuvor bearbeitet hatten, erhalten Sie keine neue Punktzahl.")
            else:
                return jsonify(success=True, resp="Sie haben alle Fragen beantwortet und dieses Labor damit abgeschlossen. Der Roboter bringt den Stern zum letzten Behälter und anschließend zurück in die Startposition. Sie haben nun insgesamt " + str(score_lab2) + " Punkte in diesem Labor erzielt und können Ihren neuen Gesamtscore auf der Startseite einsehen.")
        else:
            return jsonify(success=False, resp="Ihre Lösung ist nicht korrekt. Bitte versuchen Sie es erneut.")
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/init_quiz/', methods=['POST'])
def init2quiz():
    print(' --- lab2: init2quiz()')
    """
    Erster Aufruf des Quiz-Abschnitts
    Hier wird nur der Roboter in die Initialpose verfahren
    """
    while ReLab.glob["blocked"]:
        # vorheriger Prozess noch nicht abgeschlossen
        time.sleep(0.2)
        #print("init2quiz: waiting for blocked = False")
    try:
        ReLab.glob['blocked'] = True
        # Roboter kann im gleichen State wie in Lab1 starten
        lab2_subindex = int(ReLab.glob["lab2_subindex"][subindex_quiz0 + ReLab.glob["quiz"]["index"]])
        # int(110)  # = Labor 1 bonus 1
        print("quiz_index = " + str(ReLab.glob["quiz"]["index"]))
        print("Dieser Index müsste 110 sein:")
        print("lab2_subindex = " + str(lab2_subindex))
        tbc.send_ITP(ReLab.yu_nodes, to=5)
        while not tbc.isReady(ReLab.yu_nodes):
            time.sleep(0.1)
        tbc.sendLabNumber(ReLab.yu_nodes, lab2_subindex)
        tbc.startAction(ReLab.yu_nodes)  # Starten der Bewegung: Initialisierung Labor 1 Bonusaufgaben
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        return jsonify(sucess=True)
    except Exception as e:
        print(traceback.print_exc())
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab2/get_quiz/', methods=['GET'])
def getQuiz2():
    """
    Diese Funktion sendet das Quiz an den Client
    """
    # Antworten des Quiz shuffeln, damit Kopieren der Loesungen von Kommilitonen erschwert wird
    if not bDebugMode:
        for i in range(len(quiz_json)):
            quiz_json[i]['answers'] = random.sample(quiz_json[i]['answers'], len(quiz_json[i]['answers']))
    return jsonify(quiz_json)


@uwsgi_app.route(ReLab.mainroute + "/rest/be/CI/lab2/download/<identify>", methods=['GET'])
def download2(identify):
    """
    Es wird versucht die Datei  /exchange/Download.csv zur senden.

    :param identify: dummy-Parameter, um caching zu verhindern (URL ändert sich)
    :return: File oder Fehlermeldung
    """
    print(' ++++++++++++ lab2.py/download() ++++++++++++++')
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
