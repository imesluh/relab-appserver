"""
Hauptanwendung, die über uwsgi gestartet wird. Beinhaltet sämtliche Funktionalitäten, bis auf die Verarbeitung von Lösungsübermittlungen über das "Solution Interface" (u.a. auch der Evaluationsbogen).
"""
from apscheduler.schedulers.gevent import GeventScheduler
import gevent
from gevent import monkey

monkey.patch_all()
from flask import (
    Flask,
    Response,
    request,
    jsonify,
    send_file
)
from flask_socketio import SocketIO, emit, disconnect
import os
import time

import traceback
import json

import db_client.database_fcn as db
import testbed_communication.opcua_communication as tbc
import testbed_communication.yu_kinematics as robot
import get_passwords as get_pw

from datetime import (
    datetime
)

from db_client.db_cleaner import clean_db
import numpy as np

def clean_table():
    """
    Die Funktion setzt am Ende der Reservierung alle Werte zurück und löscht die Datei .../exchange/Dwonloads.csv.
    """
    global glob, group, yu_conn, yu_nodes
    try:
        if glob["ws_connected"]:
            print('############### clean_data###########')
            glob["ws_disconnect"] = True
    except NameError:
        pass
    try:
        reinitialize_tb()
        if not tbc.isReady(yu_nodes):
            print("Dies sollte nicht ausgeführt werden! ggf. while-Schleife einfuegen")
        tbc.turnOffLight(yu_nodes)
        tbc.disconnect(yu_conn)
    except:
        print("Failed to disconnect opcua")
        pass
    try:
        del group
    except:
        pass
    # glob = {}
    glob['blocked'] = False         # Diese bool markiert, dass noch ein eine Funktion ausgeführt wird
    glob["ws_connected"] = False    # Kein Teilnehmer ist eingeloggt und auf dem CI aktiv (keine Websocket-Verbindung ist aktiv)
    glob['download'] = ''           # Keine Date zum download vorhanden
    glob["quiz"] = {}
    glob["quiz"]["attempts"] = 0    # Anzahl der bereits eingegeben Lösungsversuche
    glob["quiz"]["index"] = 0       # Index der aktuellen Frage im Quiz
    glob["quiz"]["done"] = [False, False, False, False, False]
    ###
    glob["lab1_subindex"] = [1, 11, 12, 13, 110, 111, 112, 113, 114, 115]       # notwendig für Labor-Ablaufsteuerung auf dem Yu
    glob["lab2_subindex"] = [2, 110, 111, 112, 113, 114, 115]                   # notwendig für Labor-Ablaufsteuerung auf dem Yu
    glob["lab3_subindex"] = [3, 110, 111, 112, 113, 114, 115]                   # notwendig für Labor-Ablaufsteuerung auf dem Yu
    glob["lab4_subindex"] = [4, 110, 111, 112, 113, 114, 115]  # notwendig für Labor-Ablaufsteuerung auf dem Yu
    glob["konstants"] = {}
    glob["Done"] = False
    glob["ResetTime"] = datetime(2017, 1, 1, 0, 0)
    glob["Step"] = 0
    glob['q_rPose'] = []        # random pose Lab1
    glob['q_start_deg'] = []        # random start pose Lab3
    glob['delta_x_m'] = []          # random delta x_E (x,y,z) movement in m  (Lab 3)
    glob['score'] = [0,0,0,0,0,0,0,0]       # just for debugging reasons..
    yu_conn, yu_nodes = tbc.connect('opc.tcp://192.168.1.1:4840')
    tbc.communicate(yu_nodes, [0, 2, 3, 4], [0, 0, 0, 0], timeout=5)

    # Roboter soll anstatt einfach zu Home zu fahren, sich reinitialisieren (Stern in Ausgangslage)
    # tbc.send_ITP(yu_nodes, to=5)
    reinitialize_tb()

    try:
        os.remove(basedir + "/exchange/Download.csv")
    except:
        pass

def reinitialize_tb():
    # Roboter wieder in Initialzustand versetzen (inkl. Stern in Startposition)
    while not (tbc.communicate(yu_nodes, int(1), 1, timeout=5) == 0):
        time.sleep(0.5)
        print("Warte bis Yu bereit ist, um Ausgangszustand wiederherzustellen.")
    # TODO: muss hier auch auf glob['blocked'] gewartet werden?!
    try:
        glob['blocked'] = True
        tbc.communicate(yu_nodes, int(0), int(100), timeout=5)
        tbc.communicate(yu_nodes, int(2), 1, timeout=5)  # Starten der Bewegung
        time.sleep(0.5)
        #while not glob["ready"]:
        # hier muss direkt die tbc-Funktion abgefragt werden, da Anfangs vom Labor der "glet_ready"-Thread ggf. noch nicht aktiv ist
        while not tbc.isReady(yu_nodes):
            time.sleep(0.2)
            print("Yu stellt Ausgangstand wieder her.. ")
        time.sleep(0.2)
    except Exception as e:
        print(traceback.print_exc())
    finally:
        glob['blocked'] = False

pw_sql = get_pw.password_sql()
ip_server = get_pw.get_ip('SERVER_IP')
conn = db.connection("mysql+pymysql://relab:" + pw_sql + "@" + ip_server + ":3306/RobotikI")
sched = GeventScheduler()
sched.add_job(clean_db, 'interval', seconds=30, args=(conn,))
sched.add_job(clean_table, 'cron', minute='29,59', second=59)
g = sched.start()

uwsgi_app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))  ## Pfad der Website auf dem Server (/var/www/robotiki/app)

config_path = basedir + '/config/'
uwsgi_app.config["MAX_CONTENT_LENGTH"] = 1000000

duration = 30 * 60
uwsgi_app.secret_key = os.urandom(24)

async_mode = None#'gevent_uwsgi' # bei None sollte automatisch nach installierten Paketen ausgewählt werden (gevent_uwsgi)
#async_mode = 'threading'
socket = SocketIO(uwsgi_app, async_mode=async_mode, logger=False, engineio_logger=False)
#socket = SocketIO(uwsgi_app, async_mode=async_mode)
socket_namespace = '/data'      # muss zur Definition in websocket.js passen

# Debugging
start = datetime.now()

glob={}
glob["ws_connected"] = False
glob["ws_disconnect"] = False
glob["ready"] = True                    # Diese bool markiert, dass der Versuchsstand bereit ist
clean_table()

mainroute = '/RobotikI'

print(" ===== ReLab.py")


## Websocket-Verbindungen für Daten-Stream (kontinuierlich und binär) des Versuchsstandes und Uhr
def data_stream(socket):
    """
    Die Funktion sendet den Messvektor des Versuchsstandes an die Client-Seite.

    :param socket: Websocket-Verbindung
    :return:
    """
    global lab_number, yu_nodes
    while True:
        t, q, dq, pos = tbc.readAxValues(yu_nodes)
        if lab_number == 1:
            signal = [q[0], q[1], q[2], q[3], q[4], q[5], pos[0]*1000, pos[1]*1000, pos[2]*1000]
        else:
            signal = [q[0], q[1], q[2], q[3], q[4], q[5], pos[0]*1000, pos[1]*1000, pos[2]*1000]
        data=json.dumps({'Name': 'Data', 'Value': signal})
        socket.emit('Data_stream', data, namespace=socket_namespace)
        gevent.sleep(0.01)


def clock(socket):
    """
    #Die Funktion liefert die verbleibende Zeit (als String) auf der Website über einen Websocket-Datenstream-

    #:param socket: Websocket-Verbindung
    """
    global start, duration, glet_data, glet_time, glob
    while True:
        time_left = duration - (datetime.now()-start).total_seconds()-60
        minutes = int(time_left//60)
        seconds = int(time_left%60)
        if minutes < 10:
            str_minutes = "0" + str(minutes)
        else:
            str_minutes = str(minutes)
        if seconds < 10:
            str_seconds = "0" + str(seconds)
        else:
            str_seconds = str(seconds)
        clock = str_minutes + ":" + str_seconds
        data=json.dumps({'Name': 'Clock', 'Value': clock})
        if time_left<=0:
            #ws.send(json.dumps({'Name': 'Disco'}))
            socket.emit('Disco', namespace=socket_namespace)
            gevent.sleep(0.01)
            #ws.close() # Verbindung mit Client abbrechen
            print('###########clock#############')
            glob["ws_disconnect"] = True
        #ws.send(data)#old websocket lib
        socket.emit('Clock', data, namespace=socket_namespace)
        gevent.sleep(1)#1

def ready(socket):
    """
    Die Rückmeldung des Versuchsstandes wird in in den Arbeitsspeicher geschrieben (in glob['ready'] und
    glob['completed'])

    :param socket: Websocket-Verbindung
    """
    global glob, yu_nodes
    while True:
        state = tbc.communicate(yu_nodes,int(1),0, timeout=5)
        if state==0:
            ready = 1
        else:
            ready = 0
        data = json.dumps({'Name': 'Ready', 'Value': ready})
        glob['ready'] = ready
        socket.emit('Ready', data, namespace=socket_namespace)
        gevent.sleep(0.1)

def ws_to():
    """
    Die Funktion löscht die subprozesse (greenlets aus gevent), wenn die Websocketverbindung vom Client abgebrochen
    wurde (länger als 5 Sekunden kein traffic).
    """
    #print('############# function ws_to() #########')
    global ws_timeout, glet_data, glet_time, glob, glet_ready
    ws_timeout = datetime.now()
    while True:
        if (datetime.now()-ws_timeout).total_seconds()>5.1:
            print('##############ws_to################')
            glob["ws_disconnect"] = True
        gevent.sleep(1)



## Überprüfung der Dateiformate
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in uwsgi_app.config['ALLOWED_EXTENSIONS']


@uwsgi_app.before_request
def auth_br():
    """
    Die Funktion überprüft jeden Request, ob der user zugriffsberechtigt auf das Control-Interface ist. Dies ist eine
    Sicherung, da im Normalfall der user schon beim Aufruf der Seite in main.py zurückgewiesen wird.
    """
    global start, lab_number, glob, control_config
    user = request.environ.get('REMOTE_USER')
    req_path = request.path
    lab_request = int(req_path[(req_path.index('lab')+3)]) # Angefragte Labornummer (1-indiziert)
    start = conn.get_reservations(user)[0].reservation
    lab_number = int(conn.get_lab(user, start))+1 # reservierte Labornummer
    try:
        pass
        # Labornummer NICHT bei jedem Request an den Yu schicken. Kann u.U. zu nicht deterministischen Verhalten der State Machine fuehren
        #tbc.communicate(yu_nodes, int(0), lab_number, timeout=5)
    except:
        print("auth_br(): Something went wrong sending lab number towards yu.")
    if not user == 'imesUser':
        if (start is None) or (not lab_request==lab_number): # Wenn keine gültige Reservierung vorliegt
            return ''
        else:
            if duration < (datetime.now()-start).total_seconds()+1 or (datetime.now()-start).total_seconds()<0:
                # Wenn Laborzeit abgelaufen ist bzw. Labor noch nicht begonnen hat
                try:
                    glob["ws_disconnect"] = True
                except Exception:
                    pass
                return ''


@socket.on('my_connect', namespace=socket_namespace)  # so wird sichergestellt, dass Funkion erst ausgeführt nachdem socketIO transport auf 'websocket' geupgraded wurde
def data_feed():
    """
    Websocket-Verbindung zum Client. Es werden die Subprozesse (glet) für das Senden der Messdaten und der verbleibenden
    Zeit gestartet sowie ein Watchdog, der die WS-Verbindung schließt, wenn 5 Sekunden nichts gesendet wurde. Erhält
    die Funktion vom Client den "Content" "Disconnect", wird die Verbindung geschlossen.
    """
    global glob, yu_nodes, lab_number, control_config, start
    print('*********************** data_feed() ****************************')
    glob["ws_disconnect"] = False
    user = request.environ.get('REMOTE_USER')
    start = conn.get_reservations(user)[0].reservation
    lab_number = int(conn.get_lab(user, start)) + 1  # reservierte Labornummer
    # if False:
    if (glob["ws_connected"] or
            (start is None) or
            (duration < (datetime.now() - start).total_seconds() + 1) or
            ((datetime.now() - start).total_seconds() < 0)):  # Seite gesperrt
        emit('Blocked')
        gevent.sleep(1)
        socket.server.disconnect(sid=request.sid, namespace=socket_namespace)
    else:
        # tbc.communicate(yu_nodes, int(0), lab_number, timeout=5) Labornummer hier nicht mehr an den Yu senden, kann u.U. zu nicht deterministischem Verhalten der State Machine fuehren
        # Subprozesse für websocket timeout, data stream, ready des Versuchsstandes und Restzeit starten
        glet_ws_to = gevent.spawn(ws_to)
        glet_data = gevent.spawn(data_stream, socket)
        glet_ready = gevent.spawn(ready, socket)
        glet_time = gevent.spawn(clock, socket)
        glob['ready'] = False       # setze initial ready auf False, damit hier auf gevent-Thread "glet_ready" gewartet wird
        while glob['blocked'] or (not tbc.isReady(yu_nodes)):
            time.sleep(0.1)
            print("ReLab.data_feed(): warte bis Versuchsstand bereit und nicht blockiert..")
        try:
            glob['blocked'] = True
            # Reinitialize State anstatt HOME
            reinitialize_tb()
            #tbc.send_ITP(yu_nodes, to=5)  # home position anfahren
            while not tbc.isReady(yu_nodes):
                time.sleep(0.1)
                print("ReLab.data_feed(): waiting for ready-signal")
            tbc.communicate(yu_nodes, int(0), lab_number, timeout=5) # nochmal Labornummer senden, sonst bleibt Yu im Initial-State
        except Exception as e:
            print(traceback.print_exc())
        finally:
            glob['blocked'] = False

        while True:
            gevent.sleep(0.1)
            if (glob["ws_disconnect"]):
                print(' .... ws_disconnect')
                glob["ws_connected"] = False
                glob["ws_disconnect"] = False
                # subprozesse (greenlets aus gevent) beenden
                glet_data.kill()
                glet_time.kill()
                glet_ready.kill()
                glet_ws_to.kill()
                # disconnect() #does not work..
                print('server disconnect')
                socket.server.disconnect(sid=request.sid, namespace=socket_namespace)
                print("!!!!!!!!!!!!!!!!! gevent-threads killed. Websocke disconnected.")
                return


# boolean zur Bereinigung in data_feed()
@socket.on('Disconnect', namespace=socket_namespace)
def ws_disconnect():
    """
    Websocket Event handle auf Client-seitigen Verbindungsabbruch (Browser-Fenster wird geschlossen, Tab geschlossen, andere URL-geladen).
    """
    print('+++++++++++ ws_disconnect() ++++++++++++++++++')
    global glob
    glob["ws_disconnect"] = True
    # Variablen zur Ablaufsteuerung des Labors zurücksetzen:
    glob["quiz"]["attempts"] = 0
    glob["quiz"]["index"] = 0

    reinitialize_tb()           # Befehl an den Yu, um in den "recover" state zu gehen
    if not tbc.isReady(yu_nodes):
        print("Dies sollte nicht ausgeführt werden! ggf. while-Schleife einfuegen")
    tbc.turnOffLight(yu_nodes)


@socket.on('ws_to_ping', namespace=socket_namespace)
def reset_ws_to():
    """
    Client sided ping handle: Reset the websocket timeout for ws_to()
    """
    global ws_timeout
    ws_timeout = datetime.now()
    # print(' **********  reset ws timeout ********')

def calcQuizScore(nAttempts):
    """
    Calculate quiz score
    :param nAttempts: number of attempts to solve the question
    :type: nAttempts: int
    :return: score value
    :rtype: int
    """
    baseValue = 500
    return int(baseValue/nAttempts)

import lab1
import lab2
import lab3
import lab4
