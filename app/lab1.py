from ReLab import uwsgi_app, socket
import ReLab
import gevent
import pdb
import numpy as np
import math
from numpy.linalg import inv
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


#import database_fcn
import numpy as np

# load config file containing quiz tasks
with open(ReLab.config_path + 'quiz1.json') as config_file:
    quiz_json = json.load(config_file)

### global variables
bDebugMode = False


# alte Positionen? von Knoechelmann
positions = {1: {"cart": [0, 600, 100, 180, 0, 0], "ang": [103.32, -79.74, 107.31, -117.57, -90, -13.32]},
             2: {"cart": [200, 650, 100, 180, 0, 0], "ang": [84.62,-70.17,94.69,-114.52,-90,5.38]},
             3: {"cart": [350, 450, 100, 180, 0, 0], "ang": [66.15, -83.41, 111.65, -118.24, -90, 23.85]},
             4: {"cart": [350, -250, 100, 180, 0, 0], "ang": [-16.80, -102.61, 129.61, -116.99, -90, 106.80]},
             5: {"cart": [-300, -500, 100, 180, 0, 0], "ang": [-107.25, -81.80, 109.79, -117.98, -90, -197.25]}}#limit auf dem Yuanda Achse 6: -220° ... +220°

# geteacht von Abdullah
q_container = [[-108.92, -80.61, 110.9, -120.16, -90.27, 108.16],
                 [-17.31, 102.55, 132.56, -121.05, -88.32, 16.59],
                 [64.82, -82.42, 113.08, -120.59, -89.56, 23.5],
                 [83.27, -69.27, 95.75, -116.12, -89.49, 96.58],
                 [102.49, -78.95, 108.97, -119.85, -88.89, 75.98]]
#q_Stern_verdreht = [-18.829999966193707, -97.2962359721284, 134.68506031899338, -127.63881860515478, -90.00000250447816, 16.10000147262717]
#q_SternStart = [-18.829999966193707, -97.2962359721284, 134.68506031899338, -127.63881860515478, -90.00000250447816, 106.10000147262717]
#q_SternZiel = [-108.52999836421012, -80.00574869202453, 112.40302981230916, -122.90727335952015, -89.82999909603654, 197.15999469477794]
q_contA = [-108.52999836421012, -80.00574869202453, 112.40302981230916, -122.90727335952015, -89.82999909603654, 197.15999469477794]
q_contB = [-18.829999966193707, -97.2962359721284, 134.68506031899338, -127.63881860515478, -90.00000250447816, 106.10000147262717]
#q_contB_turned = q_Stern_verdreht
q_random = [
    #[0, -90, 90, -90, -90, 0],
    #[-8.71, -108.16, 105.22, -87.07, -90, 8.71],
    #[9.12, -115.66, 107.45, -81.79, -90, -9.12],
    #[28.07, -103.79, 83.53, -69.74, -90, -27],
    [35.58, -101.03, 123.09, -112.06, -90, -34.62],
    [78.05, -97.36, 120.12, -112.76, -90, -77.08],
    [135.31, -97.33, 120.09, -112.76, -90, -90.15],
    [71.18, -80, 90, -164, -105, -30],
    [16, -113, 118, -180, -71.5, -90],
    [-27, -71, 93, -146, -57, -60],
    [-70, -74.15, 80.54, -58.48, -110, -20],
    [-128.72, -78.8, 74.15, -172, -90, 0],
    [-169.5, -87, 82, -263, -90, 0],
    [92, -90, 86, -180, -80, 0],
    [90, -90, 0, -180, -90, 0],
    [37, -53, 86, -213, -76, 0],
    [0, -90, 0, -90, 0, 0],
    [0, -90, 90, -180, 90, -90],
    [-30, -60, 80, -180, -70, -90],
    [30, -50, 70, -150, -80, -105]
]

def funktions_muster():
    if ReLab.glob['blocked']:
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        """
        put your code here
        """
        return jsonify(success=True, resp='Text')
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/toggle_debug/', methods=['POST'])
def toggle_debug():
    """
    Debug-Modus wird an/ausgeschaltet
    """
    global bDebugMode
    print(' --- lab1: toggle_debug()')
    user = request.environ.get('REMOTE_USER')
    if not ReLab.conn.is_imes_user(user):
        return jsonify(success=False,resp="No permission to change debug mode.")
    else:
        receive_data = request.get_json()         # Nutzereingabe abfragen
        print(receive_data)
        bDebugMode = receive_data['bDebug']   # user input
        return jsonify(success=True,resp="Toggled debug mode.")

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/initCI/', methods=['GET'])
def init1CI():
    print(' --- lab1: initCI()')
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
        return jsonify(b_imesUser=True)


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/init/', methods=['GET'])
def init1():
    """
    Erster Aufruf der Control Interface Seite
    Roboter wird in Zwischenpose verfahren, in welcher der Stern (in Behaelter Nr. 2) in der Yu-Kamera sichtbar ist.
    """
    print(' --- lab1: init1()')
    ReLab.reinitialize_tb()

    idx_rand = np.random.randint(0, len(q_random))  # pick random pose
    ReLab.glob['q_rPose'] = q_random[idx_rand]
    q_target = ReLab.glob['q_rPose']
    # send robot pose to user
    pose_target = robot.direct_kinematics(np.array(q_target))[0][:, 5]
    pose_target = [round(item, 5) for item in pose_target]


    # for task A: calculate translation and euler angles and send to user
    r_OE, eul_OE, r_OB, eul_OB = getValues_a(q_contB, q_target)
    # change units (degree + mm)
    r_OE = (r_OE * 1000).round(3)
    r_OB = (r_OB * 1000).round(3)
    eul_OE = (robot.rad2deg(eul_OE)).round(3)
    eul_OB = (robot.rad2deg(eul_OB)).round(3)

    # for task B: calculate given parameters and send to user
    quat_A, Or_A, Or_B, eulxyz_B = getValues_b(q_contB, q_contA)
    quat_A = quat_A.round(6)
    Or_A = (Or_A * 1000).round(3)
    Or_B = (Or_B * 1000).round(3)
    eulxyz_B = (robot.rad2deg(eulxyz_B)).round(3)

    # for task C: alculate given parameters and send to user
    Ar_B, theta_AB, u_AB = getValues_c(q_contA, q_contB)
    Ar_B = (Ar_B * 1000).round(3)
    theta_AB = (robot.rad2deg(theta_AB)).round(3)
    u_AB = u_AB.round(5)

    # build return json:
    rVal = jsonify(sucess=True, a_r_OE=r_OE.tolist(), a_eul_OE=eul_OE.tolist(), a_r_OB=r_OB.tolist(), a_eul_OB=eul_OB.tolist(),
                   b_quat_A=quat_A.tolist(), b_Or_A=Or_A.tolist(), b_Or_B=Or_B.tolist(), b_eulxyz_B=eulxyz_B.tolist(),
                   c_Ar_B=Ar_B.tolist(), c_theta_AB=[theta_AB], c_u_AB=u_AB.tolist())
    ######## debug, reconnect to aborted session
    #return jsonify(sucess=True, transl=r_ES.tolist(), rot=eulxyz.tolist(), goto=3)
    ########

    time.sleep(5)  # wait for greenlet processes (dort werden ITPs an den Yu gesendet)
    print(q_target)
    for winkel, achse in zip(q_target, range(len(q_target))):
        tbc.communicate(ReLab.yu_nodes, [3, 4], [achse + 1, winkel * 100], timeout=5)     # send actor values to the Yu

    tbc.communicate(ReLab.yu_nodes, int(2), 1, timeout=5)     # start moving
    time.sleep(0.5)
    while not ReLab.glob["ready"]:
        time.sleep(0.1)   # wait for robot reaching target pose
        print("lab1 init1(): waiting for ready-signal")
    return rVal
    # return jsonify(sucess=True, a_transl=r_ES.tolist(), a_rot=eulxyz.tolist(),
    #         b_quat_Z=quat_Z.tolist(), b_Or_Z=Or_Z.tolist(), b_Or_S=Or_S.tolist(), b_eul_S=eul_S.tolist(),
    #         c_Or_S_neu=Or_S_neu.tolist(), c_theta_S_neu=[theta_S_neu], c_u_S_neu=u_S_neu.tolist())
    #return jsonify(sucess=True, transl=r_ES.tolist(), rot=eulxyz.tolist())

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/send_1a/', methods=['POST'])
def send1a():
    """
    Die übermittelte Lösung (Transformationsmatrix) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab1: send1a()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)
    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        receive_data = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')

    try:
        ReLab.glob['blocked'] = True
        receive_data = request.get_json()         # Nutzereingabe abfragen
        ET_S = np.array(receive_data['Tmat'])   # user input
        bCorrectA = accept_a(ET_S, q_contB, ReLab.glob['q_rPose']) # Vom Studi bestimmte Trafo ET_S wird überprüft

        if bCorrectA:
            # Score schreiben
            ms = ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)
            idx_ms = 0
            if not ms[idx_ms]:   # Milestone zuvor noch nicht erreicht
                score = 500 + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
                ReLab.glob['score'][idx_ms] = score
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, idx_ms)
            return jsonify(success=True,resp="Die übermittelte Lösung ist korrekt, Sie erhalten 500 Punkte. Sie können den Roboter nun zum Stern verfahren.")
        else:
            return jsonify(success=False, resp="Lösung nicht korrekt. Bitte versuchen Sie es erneut.")
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/start_1a/', methods=['POST'])
def start1a():
    """
    Nach richtiger Lösungsübermittlung kann der Stern angefahren werden.
    """
    print(' --- lab1: start1a()')
    if ReLab.glob['blocked']:
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        tbc.communicate(ReLab.yu_nodes, int(0), int(11), timeout=5)
        glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                 [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                 ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                 ReLab.yu_nodes, 'extern')
        tbc.communicate(ReLab.yu_nodes, int(2), 1, timeout=5)  # Starten der Bewegung
        time.sleep(0.5)
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        time.sleep(0.2)
        glet_recv.kill()
        return jsonify(success=True,resp="Der Stern wurde erfolgreich gegriffen. Sie können nun mit dem nächsten Aufgabenteil fortfahren.")
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/send_1b/', methods=['POST'])
def send1b():
    """
    Die übermittelte Lösung (Transformationsmatrix) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab1: send1b()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)
    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        receive_data = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        receive_data = request.get_json()         # Nutzereingabe abfragen
        #print(receive_data)
        ST_Z = np.array(receive_data['Tmat'])

        bCorrectB = accept_b(ST_Z, q_contB, q_contA) # Vom Studi bestimmte Trafo ST_Z wird überprüft
        #print("Uebermittelte Loesung: " + str(ST_Z))

        if bCorrectB:
            # Score schreiben
            ms = ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)
            idx_ms = 1
            if not ms[idx_ms]:  # Milestone zuvor noch nicht erreicht
                score = 500 + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
                ReLab.glob['score'][idx_ms] = 500
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, idx_ms)
            return jsonify(success=True,resp="Die übermittelte Lösung ist korrekt, Sie erhalten 500 Punkte. Sie können den Roboter nun zum Ziel verfahren.")
        else:
            return jsonify(success=False, resp="Lösung nicht korrekt. Bitte versuchen Sie es erneut.")
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/start_1b/', methods=['POST'])
def start1b():
    """
    Nach richtiger Lösungsübermittlung kann der Zielbehaelter angefahren werden.
    """
    print(' --- lab1: start1b()')
    if ReLab.glob['blocked']:
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        tbc.communicate(ReLab.yu_nodes, int(0), int(12), timeout=5)
        glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                 [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                 ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                 ReLab.yu_nodes, 'extern')
        tbc.communicate(ReLab.yu_nodes, int(2), 1, timeout=5)  # Starten der Bewegung
        time.sleep(0.5)
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        time.sleep(0.2)
        glet_recv.kill()
        return jsonify(success=True, resp="Der Zielbehälter wurde erfolgreich angefahren. Sie können nun mit dem nächsten Aufgabenteil fortfahren.")
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/send_1c/', methods=['POST'])
def send1c():
    """
    Die übermittelte Lösung (Transformationsmatrix) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab1: send1c()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)
    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        receive_data = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')

    try:
        ReLab.glob['blocked'] = True
        receive_data = request.get_json()         # Nutzereingabe abfragen
        ZT_S = np.array(receive_data['Tmat'])
        bCorrectC = accept_c(ZT_S, q_contA, q_contB)  # Vom Studi bestimmte Trafo ZT_S wird überprüft

        if bCorrectC:
            # Score schreiben
            ms = ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)
            idx_ms = 2
            if not ms[idx_ms]:  # Milestone zuvor noch nicht erreicht
                score = 500 + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
                ReLab.glob['score'][idx_ms] = 500
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, idx_ms)
            return jsonify(success=True,resp="Die übermittelte Lösung ist korrekt, Sie erhalten 500 Punkte. Sie können den Roboter nun zum Ziel verfahren.")
        else:
            return jsonify(success=False, resp="Lösung nicht korrekt. Bitte versuchen Sie es erneut.")
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/start_1c/', methods=['POST'])
def start1c():
    """
    Nach richtiger Lösungsübermittlung kann der Zielbehaelter angefahren werden.
    """
    print(' --- lab1: start1c()')
    if ReLab.glob['blocked']:
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        tbc.communicate(ReLab.yu_nodes, int(0), int(13), timeout=5)
        glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                 [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                 ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                 ReLab.yu_nodes, 'extern')
        tbc.communicate(ReLab.yu_nodes, int(2), 1, timeout=5)  # Starten der Bewegung
        time.sleep(0.5)
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        time.sleep(0.2)
        glet_recv.kill()
        return jsonify(success=True,resp="Der Zielbehälter wurde erfolgreich angefahren. Sie können nun mit dem nächsten Aufgabenteil fortfahren.")
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/send_1quiz/', methods=['POST'])
def send1quiz():
    """
    Die übermittelte Lösung (Quiz-Antworten) wird überprüft und die Position angefahren, falls die Lösung richtig ist.
    """
    print(' --- lab1: send1quiz()')
    user = request.environ.get('REMOTE_USER')
    group = ReLab.conn.get_group(user)
    if ReLab.glob['blocked']:  # Wenn eine andere Funktion noch ausgeführt wird
        receive_data = request.get_json()
        return jsonify(success=False, resp='Warten Sie bitte, bis der vorherige Prozess abgeschlossen ist.')
    try:
        ReLab.glob['blocked'] = True
        receive_data = request.get_json()         # Nutzereingabe abfragen
        #print(receive_data)
        bAnswer = receive_data['checked']           # read checked boxes
        bAnswerCorrect = [dictAnsw['truth'] for dictAnsw in quiz_json[receive_data['nQuestion']-1]['answers'] if 'truth' in dictAnsw]

        if bDebugMode:
            bAnswer = bAnswerCorrect

        # print("bAnswer: " + str(bAnswer))
        # print("bAnswerCorr: " + str(bAnswerCorrect))

        ReLab.glob["quiz"]["attempts"] = ReLab.glob["quiz"]["attempts"] + 1

        if bAnswer == bAnswerCorrect:
            # Score und Milestone in DB schreiben
            idx_ms = ReLab.glob["quiz"]["index"] + 3
            print("idx Milestone: " + str(idx_ms))
            bFirstTry = False
            if not(ReLab.conn.get_milestones(user, int(ReLab.lab_number) - 1)[idx_ms]):
                bFirstTry = True
                score = ReLab.calcQuizScore(ReLab.glob["quiz"]["attempts"])
                score_lab1 = ReLab.calcQuizScore(ReLab.glob["quiz"]["attempts"]) + ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
                ReLab.glob['score'][idx_ms] = ReLab.calcQuizScore(ReLab.glob["quiz"]["attempts"])
                print("Score: " + str(ReLab.glob['score']))
                ReLab.conn.write_score(group, int(ReLab.lab_number) - 1, score_lab1)
                ReLab.conn.write_milestone(user, int(ReLab.lab_number) - 1, ReLab.glob["quiz"]["index"] + 3)
            ReLab.glob["quiz"]["done"][ReLab.glob["quiz"]["index"]] = True
            ReLab.glob["quiz"]["index"] = ReLab.glob["quiz"]["index"] +1
            ReLab.glob["quiz"]["attempts"] = 0

            # Roboter zum nächsten Stern verfahren
            lab1_subindex = int(ReLab.glob["lab1_subindex"][ReLab.glob["quiz"]["index"] + 4])
            #int(111)  # = Labor 1 bonus 1
            print("lab1_subindex = " + str(lab1_subindex))
            tbc.communicate(ReLab.yu_nodes, int(0), lab1_subindex, timeout=5)
            glet_recv = gevent.spawn(tbc.write_target_data, 'Download.csv', ReLab.basedir,
                                     [0, 1, 2, 3, 4, 5, 12, 13, 14],
                                     ['t', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'x', 'y', 'z'],
                                     ReLab.yu_nodes, 'extern')
            time.sleep(0.1)
            tbc.communicate(ReLab.yu_nodes, int(2), 1, timeout=5) # Starten der Bewegung
            # while not (tbc.communicate(ReLab.yu_nodes, int(1), 1, timeout=5) == 0):
            #     time.sleep(0.5)
            while not ReLab.glob["ready"]:
                time.sleep(0.1)
            time.sleep(0.2)
            glet_recv.kill()
            score_lab1 = ReLab.conn.get_labScore(group, int(ReLab.lab_number) - 1)
            if lab1_subindex < 115:
                if bFirstTry:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Sie erhalten entsprechend der Anzahl Ihrer Versuche " + str(score) + " Punkte.")
                else:
                    return jsonify(success=True, resp="Ihre Antwort ist korrekt. Da Sie die Aufgabe bereits zuvor bearbeitet hatten, erhalten Sie keine neue Punktzahl.")
            else:
                return jsonify(success=True, resp="Sie haben alle Fragen beantwortet und dieses Labor damit abgeschlossen. Der Roboter bringt den Stern zum letzten Behälter und anschließend zurück in die Startposition. Sie haben nun insgesamt " + str(score_lab1) + " Punkte in diesem Labor erzielt und können Ihren neuen Gesamtscore auf der Startseite einsehen.")
        else:
            return jsonify(success=False, resp="Ihre Lösung ist nicht korrekt. Bitte versuchen Sie es erneut.")
    except Exception as Argument:
        print("--- Exception send1quiz():")
        print(str(Argument))
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False

@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/init_quiz/', methods=['POST'])
def init1quiz():
    print(' --- lab1: init1quiz()')
    """
    Erster Aufruf des Quiz-Abschnitts
    Hier wird nur der Roboter in die Initialpose verfahren
    """
    while ReLab.glob["blocked"]:
        # vorheriger Prozess noch nicht abgeschlossen
        time.sleep(0.2)
        print("init1quiz: waiting for blocked = False")
    try:
        ReLab.glob['blocked'] = True
        # tbc.send_ITP(ReLab.yu_nodes, to=5)  # move Yu into home position
        lab1_subindex = int(ReLab.glob["lab1_subindex"][4 + ReLab.glob["quiz"]["index"]])
        # int(110)  # = Labor 1 bonus 1
        print("quiz_index = " + str(ReLab.glob["quiz"]["index"]))
        print("lab1_subindex = " + str(lab1_subindex))
        tbc.communicate(ReLab.yu_nodes, int(0), lab1_subindex, timeout=5)
        time.sleep(0.2)
        tbc.communicate(ReLab.yu_nodes, int(2), 1,
                        timeout=5)  # Starten der Bewegung: Initialisierung Labor 1 Bonusaufgaben
        # while not (tbc.communicate(ReLab.yu_nodes, int(1), 1, timeout=5) == 0):
        #     time.sleep(0.5)
        time.sleep(0.2)
        while not ReLab.glob["ready"]:
            time.sleep(0.1)
        return jsonify(sucess=True)
    except:
        return jsonify(success=False, resp='Irgendetwas ist schief gelaufen. Bitte versuchen Sie es erneut.')
    finally:
        ReLab.glob['blocked'] = False


@uwsgi_app.route(ReLab.mainroute + '/rest/be/CI/lab1/get_quiz/', methods=['GET'])
def getQuiz():
    """
    Diese Funktion sendet das Quiz an den Client
    """
    # Antworten des Quiz shuffeln, damit Kopieren der Loesungen von Kommilitonen erschwert wird
    ## auskommentiert zum DEBUGGEN
    ## TLH-MARKER
    if not bDebugMode:
        for i in range(len(quiz_json)):
            quiz_json[i]['answers'] = random.sample(quiz_json[i]['answers'], len(quiz_json[i]['answers']))
    return jsonify(quiz_json)


@uwsgi_app.route(ReLab.mainroute + "/rest/be/CI/lab1/download/<identify>", methods=['GET'])
def download1(identify):
    """
    Es wird versucht die Datei  /exchange/Download.csv zur senden.

    :param identify: dummy-Parameter, um caching zu verhindern (URL ändert sich)
    :return: File oder Fehlermeldung
    """
    print(' ++++++++++++ lab1.py/download() ++++++++++++++')
    if not ReLab.glob['blocked']:
        try:
            ReLab.glob['blocked'] = True
            return send_file(ReLab.basedir + "/exchange/Download.csv", mimetype="text/csv", as_attachment=True,
                             attachment_filename="data.csv")
        except:
            traceback.print_exc()
            return Response('Es existiert keine Datei zum Download.')
        finally:
            ReLab.glob['blocked'] = False
    else:
        return Response("Bitte warten Sie, bis der vorherige Prozess abgeschlossen ist.")


# -------------------- Loesungsueberpruefung, ect
"""
Funktionen zur Loesungsueberpruefung
Autor: Abdullah, Sterneck
"""

def getValues_a(q_contB, q_E):
    """
    Die den Studenten zur Verfügung gestellten Parameter werden berechnet
    Eiheiten in m und rad
    """
    # Die Matrizen OT_S und OT_Z werden aus der direkten Kinematik des YUs bestimmt
    OT_B = robot.direct_kinematics(np.array(q_contB) * np.pi / 180)[1][:, :, -1]
    OT_E = robot.direct_kinematics(np.array(q_E) * np.pi / 180)[1][:, :, -1]
    R_OB = OT_B[0:3, 0:3]
    r_OB = OT_B[0:3, -1]  # Translation EE -> Stern
    # Euler ZXZ entspricht X-Konvention
    eulzxz_OB = robot.r2eulzxz(R_OB)
    R_OE = OT_E[0:3, 0:3]
    r_OE = OT_E[0:3, -1]  # Translation EE -> Stern
    # Euler ZXZ entspricht X-Konvention
    eulzxz_OE = robot.r2eulzxz(R_OE)
    return r_OE, eulzxz_OE, r_OB, eulzxz_OB

def sol_a_hotfix(r_OE, eulzxz_OE, r_OB, eulzxz_OB):
    """
    Loesung aus Grader kopiert
    """
    #print("hotfix A")
    #print("r_0E:")
    #print(r_OE)
    r_E = r_OE
    r_B = r_OB
    #% Orientierung in Euler ZXZ
    phi_E = eulzxz_OE
    phi_B = eulzxz_OB

    #% Rotationsmatrix R_0_B
    cz1 = math.cos(phi_B[0])
    sz1 = math.sin(phi_B[0])
    cx = math.cos(phi_B[1])
    sx = math.sin(phi_B[1])
    cz2 = math.cos(phi_B[2])
    sz2 = math.sin(phi_B[2])
    R_O_B_1 = np.array([[cz1, -sz1, 0],
                        [sz1, cz1, 0],
                        [0, 0, 1]])
    R_O_B_2 = np.array([[1, 0, 0],
                        [0, cx, -sx],
                        [0, sx, cx]])
    R_O_B_3 = np.array([[cz2, -sz2, 0],
                        [sz2, cz2, 0],
                        [0, 0, 1]])
    R_O_B = np.matmul(np.matmul(R_O_B_1, R_O_B_2), R_O_B_3)

    #% Rotationsmatrix R_0_E
    cz1 = math.cos(phi_E[0])
    sz1 = math.sin(phi_E[0])
    cx = math.cos(phi_E[1])
    sx = math.sin(phi_E[1])
    cz2 = math.cos(phi_E[2])
    sz2 = math.sin(phi_E[2])
    R_0_E_1 = np.array([[cz1, -sz1, 0],
                        [sz1, cz1, 0],
                        [0, 0, 1]])
    R_0_E_2 = np.array([[1, 0, 0],
                        [0, cx, -sx],
                        [0, sx, cx]])
    R_0_E_3 = np.array([[cz2, -sz2, 0],
                        [sz2, cz2, 0],
                        [0, 0, 1]])
    R_0_E = np.matmul(np.matmul(R_0_E_1, R_0_E_2), R_0_E_3)

    #% Transformationsmatrizen
    T_0_E = robot.transRot2T(r_E,R_0_E)
    T_0_B = robot.transRot2T(r_B, R_O_B)
    T_E_B = np.matmul(inv(T_0_E), T_0_B)
    return T_E_B

def accept_a(ET_B, q_contB, q_E):
    """
    Die übermittelte Loesung wird überprüft.
    Stern liegt in Behälter B
    
    :param ET_B: User-Loesung der Transformationsmatrix von (KS)E zu (KS)S
    :type ET_B: np.mat (4x4)
    :param q_contB: Gelenkwinkelvektor (in Grad) in der SternStart Pose
    :type q_contB: list (double) (1x6)
    :param q_E: Gelenkwinkelvektor (in Grad) in der random Target Pose
    :type q_E: list (double) (1x6)
    :return: Korrektheit der Loesung
    :rtype: bool
    """
    # if there is a None in user input: fill matrix with zeros
    for matRow in ET_B:
        if None in matRow:
            ET_B = np.zeros((4,4))

    # ET_B_correct soll eigentlich durch die Bilderkennung ermittelt werden. Hier vorerst aus bekannten Transformationen.
    OT_B = robot.direct_kinematics(np.array(q_contB) * np.pi / 180)[1][:,:,-1]
    OT_E = robot.direct_kinematics(np.array(q_E) * np.pi / 180)[1][:,:,-1]

    # Berechnung der korrekten Lösung
    ET_B_correct = np.matmul(inv(OT_E),OT_B)

    # hotfix
    r_OE, eulzxz_OE, r_OB, eulzxz_OB = getValues_a(q_contB, q_E)
    ET_B_correct = sol_a_hotfix(r_OE, eulzxz_OE, r_OB, eulzxz_OB)

    # DEBUG: Loesung ueberschreiben
    # TLH-MARKER
    if bDebugMode:
        ET_B_correct = np.matrix([[1.0, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
        ET_B = ET_B_correct

    # Studi-Loesung von mm in m umrechnen
    ET_B[0: 3, 3] = ET_B[0: 3, 3] /1000  # Translation in m
    # Runden zum Vergleich mit Loesung
    ET_B_correct = np.around(ET_B_correct, 3)
    ET_B = np.around(ET_B, 3)

    print("A: Grader")
    print(ET_B_correct)
    print("A: Studi")
    print(ET_B)

    # Elementweiser Vergleich der Matrizen
    if np.allclose(ET_B, ET_B_correct, atol=1e-5, rtol=1e-5):
        return True
    else:
        return False

def getValues_b(q_B, q_A):
    """
    Start, Ziel : B, A
    Die den Studenten zur Verfügung gestellten Parameter werden berechnet
    Eiheiten in m und rad
    """

    OT_B = robot.direct_kinematics(np.array(q_B) * np.pi / 180)[1][:, :, -1]
    OT_A = robot.direct_kinematics(np.array(q_A) * np.pi / 180)[1][:, :, -1]

    quat_A = robot.r2quat(OT_A)
    Or_A = OT_A[0:3, 3]
    Or_B = OT_B[0:3, 3]
    OR_B = OT_B[0:3, 0:3]
    # Kardan entspricht Euler XYZ
    eulxyz_B = robot.r2eulxyz(OR_B)
    return quat_A, Or_A, Or_B, eulxyz_B

def sol_b_hotfix(quat_A, Or_A, Or_B, eulxyz_B):
    """
    Loesung aus Grader kopiert
    """
    q_0_A = quat_A
    r_A = Or_A

    # Rotationsmatrizen
    cx = math.cos(eulxyz_B[0])
    sx = math.sin(eulxyz_B[0])
    cy = math.cos(eulxyz_B[1])
    sy = math.sin(eulxyz_B[1])
    cz = math.cos(eulxyz_B[2])
    sz = math.sin(eulxyz_B[2])
    R_0_B_1 = np.array([[1, 0, 0],
                        [0, cx, -sx],
                        [0, sx, cx]])
    R_0_B_2 = np.array([[cy, 0, sy],
                        [0, 1, 0],
                        [-sy, 0, cy]])
    R_0_B_3 = np.array([[cz, -sz, 0],
                        [sz, cz, 0],
                        [0, 0, 1]])
    R_0_B = np.matmul(np.matmul(R_0_B_1, R_0_B_2), R_0_B_3)
    q0 = q_0_A[0]
    q1 = q_0_A[1]
    q2 = q_0_A[2]
    q3 = q_0_A[3]
    R_0_A = np.array([  [q0**2+q1**2-q2**2-q3**2, 2*q1*q2+2*q0*q3, 2*q1*q3-2*q0*q2],
                        [2*q1*q2-2*q0*q3, q0**2-q1**2+q2**2-q3**2, 2*q2*q3+2*q0*q1],
                        [2*q1*q3+2*q0*q2, 2*q2*q3-2*q0*q1, q0**2-q1**2-q2**2+q3**2]])
    R_0_A = R_0_A.transpose()

    #print('###### R_0_A')
    #print(R_0_A)
    R_0_A = robot.quat2r(quat_A)
    #print(R_0_A)

    # Transformationsmatrizen
    T_0_B = robot.transRot2T(Or_B, R_0_B)
    T_0_A = robot.transRot2T(Or_A, R_0_A)
    T_B_A = np.matmul(inv(T_0_B), T_0_A)

    return T_B_A

def accept_b(BT_A, q_contB, q_contA):
    """
    Die übermittelte Loesung wird überprüft.
    :param ST_Z: User-Loesung der Transformationsmatrix von (KS)S zu (KS)Z
    :type ST_Z: np.mat (4x4)
    :param q_contB: Gelenkwinkelvektor (in Grad) in der SternStart Pose
    :type q_contB: list (double) (1x6)
    :param q_contA: Gelenkwinkelvektor (in Grad) in der SternZiel Pose
    :type q_contA: list (double) (1x6)
    :return: Korrektheit der Loesung
    :rtype: bool
    """
    # if there is a None in user input: fill matrix with zeros
    for matRow in BT_A:
        if None in matRow:
            BT_A = np.zeros((4, 4))

    #Die Matrizen OT_S und OT_Z werden aus der direkten Kinematik des YUs bestimmt
    OT_B = robot.direct_kinematics(np.array(q_contB) * np.pi / 180)[1][:,:,-1]
    OT_A = robot.direct_kinematics(np.array(q_contA) * np.pi / 180)[1][:,:,-1]

    # +++Berechnung der den Studis gegebenen Werten und daraus der korrekten Loesung. Index "c" fuer correct
    quat_A, Or_A, Or_B, eulxyz_B = getValues_b(q_contB, q_contA)
    OR_A = robot.quat2r(quat_A)
    OR_B = robot.eulxyz2r(eulxyz_B)
    OT_B_c = robot.transRot2T(Or_B, OR_B)
    OT_A_c = robot.transRot2T(Or_A, OR_A)
    BT_A_c = np.matmul(inv(OT_B_c), OT_A_c)
    # +++

    # ~~~ Berechnung der korrekten Lösung direkt über Transformationsmatrizen
    BT_A_correct = np.matmul(inv(OT_B), OT_A)
    # hotfix: von Grader
    BT_A_correct= sol_b_hotfix(quat_A, Or_A, Or_B, eulxyz_B)
    # ~~~

    # DEBUG: Loesung ueberschreiben
    if bDebugMode:
        BT_A_correct = np.matrix([[1.0, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
        BT_A = BT_A_correct

    # Studi-Loesung von mm in m umrechnen
    BT_A[0: 3, 3] = BT_A[0: 3, 3] / 1000  # Translation in m
    # Runden zum Vergleich
    BT_A_c = np.around(BT_A_c, 3)
    BT_A_correct = np.around(BT_A_correct, 3)
    BT_A = np.around(BT_A, 3)

    print("B: Grader")
    print(BT_A_correct)
    print("B: Studi")
    print(BT_A)

    # Elementweiser Vergleich der Matrizen
    if np.allclose(BT_A, BT_A_correct, atol=1e-5, rtol=1e-5):
        return True
    else:
        return False

def getValues_c(q_contA, q_contB):
    """
    Die den Studenten zur Verfügung gestellten Parameter werden berechnet
    Eiheiten in m und rad
    """
    # Die Matrizen OT_A und OT_B werden aus der direkten Kinematik des YUs bestimmt
    OT_A = robot.direct_kinematics(np.array(q_contA) * np.pi / 180)[1][:, :, -1]
    OT_B = robot.direct_kinematics(np.array(q_contB) * np.pi / 180)[1][:, :, -1]

    # hom. Transformationsmatrix mit Rotation um 90Grad um die z-Achse
    BT_B_turned = np.array([  [0, -1, 0, 0],
                            [1, 0, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1]])
    OT_B_turned = np.matmul(OT_B, BT_B_turned)
    AT_B_turned = np.matmul(inv(OT_A), OT_B_turned)

    AT_B = np.matmul(inv(OT_A), OT_B)
    Ar_B = AT_B[0:3, 3]
    AR_B = AT_B[0:3, 0:3]
    theta_AB, u_AB = robot.r2angvec(AR_B)

    return Ar_B, theta_AB, u_AB
    # Or_S_neu = OT_S_neu[0:3, 3]
    # OR_S_neu = OT_S_neu[0:3, 0:3]
    # theta_S_neu, u_S_neu = robot.r2angvec(OR_S_neu)
    #
    # return Or_S_neu, theta_S_neu, u_S_neu

def sol_c_hotfix(Ar_B, theta_AB, u_AB):
    """
    Loesung aus Grader kopiert
    """
    print("r_A_B")
    print(Ar_B)
    print("u_A_B")
    print(u_AB)
    print("theta_AB")
    print(theta_AB)

    #% Rotationsmatrix
    u1 = u_AB[0]
    u2 = u_AB[1]
    u3 = u_AB[2]
    st = math.sin(theta_AB)
    ct = math.cos(theta_AB)
    R_A_B = np.array([  [u1**2*(1-ct)+ct, u1*u2*(1-ct)-u3*st, u1*u3*(1-ct)+u2*st],
                        [u1*u2*(1-ct)+u3*st, u2**2*(1-ct)+ct, u2*u3*(1-ct)-u1*st],
                        [u1*u3*(1-ct)-u2*st, u2*u3*(1-ct)+u1*st, u3**2*(1-ct)+ct]])
    print("R_A_B")
    print(R_A_B)

    # Transformationsmatrizen
    T_A_B = robot.transRot2T(Ar_B, R_A_B)
    print("T_A_B")
    print(T_A_B)
    T_B_B_star = np.array([ [0, -1, 0, 0],
                            [1, 0, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1]])
    #% Transformation vom Ziel zum Start (90grd gegenueber KSB verdreht)
    T_A_B_star = np.matmul(T_A_B, T_B_B_star)
    print("T_A_B_star")
    print(T_A_B_star)

    return T_A_B_star

def accept_c(AT_B_turn, q_contA, q_contB):
    """
    Die übermittelte Loesung wird überprüft.
    :param AT_B_turn: User-Loesung der Transformationsmatrix von (KS)A zu (KS)B* bei dem um +90° um die z-Achse gedreht wurde
    :type AT_B_turn: np.mat (4x4)
    :param q_contA: Gelenkwinkelvektor (in Grad) in der Pose beim Behälter A
    :type q_contA: list (double) (1x6)
    :param q_contB: Gelenkwinkelvektor (in Grad) in der Pose beim Behälter B um 90° verdreht
    :type q_contB: list (double) (1x6)
    :return: Korrektheit der Loesung
    :rtype: bool
    """
    for matRow in AT_B_turn:
        if None in matRow:
            AT_B_turn = np.zeros((4, 4))

    # Die Matrizen OT_A und OT_B werden aus der direkten Kinematik des YUs bestimmt
    OT_A = robot.direct_kinematics(np.array(q_contA) * np.pi / 180)[1][:, :, -1]
    OT_B = robot.direct_kinematics(np.array(q_contB) * np.pi / 180)[1][:, :, -1]

    #### Berechnung der korrekten Lösung
    Ar_B, theta_AB, u_AB = getValues_c(q_contA, q_contB)
    AR_B = robot.angvec2r(u_AB, theta_AB)
    AT_B = robot.transRot2T(Ar_B, AR_B)
    # hom. Transformationsmatrix mit Rotation um 90Grad um die z-Achse
    BT_B_turned = np.array([[0, -1, 0, 0],
                            [1, 0, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1]])
    AT_B_turn_corr = np.matmul(AT_B, BT_B_turned)
    # hotfix
    AT_B_turn_corr = sol_c_hotfix(Ar_B, theta_AB, u_AB)

    ### Check über direkte Berechnung der Hom. Transformationsmatrix
    OT_B_turned = np.matmul(OT_B, BT_B_turned)
    AT_B_turn_check = np.matmul(inv(OT_A), OT_B_turned)

    # DEBUG: Loesung ueberschreiben
    # TLH-MARKER
    if bDebugMode:
        AT_B_turn_corr = np.matrix([[1.0, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
        AT_B_turn = AT_B_turn_corr

    # Studi-Loesung von mm in m umrechnen
    AT_B_turn[0: 3, 3] = AT_B_turn[0: 3, 3] / 1000  # Translation in m
    # Runden zum Vergleich
    AT_B_turn_corr = np.around(AT_B_turn_corr, 3)
    AT_B_turn = np.around(AT_B_turn, 3)

    print("C: Grader")
    print(AT_B_turn_corr)
    print("C: Studi")
    print(AT_B_turn)
    #pdb.set_trace()
    # Elementweiser Vergleich der Matrizen
    if np.allclose(AT_B_turn, AT_B_turn_corr, atol=1e-5, rtol=1e-5):
        return True
    else:
        return False

