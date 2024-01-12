# ReLab Application Server: Robotik I
-----------------------

Dieses Repository enthält den Application Server für das ReLab Labor Robotik I.
Bitte zunächst die allgemeine Dokumentation des Hauptservers lesen.

## Beschreibung
Das Remote Laboratory verteilt sich über mehrere Server. Neben dem Hauptserver, auf dem der Webserver (nginx) sowie die Nutzerdatenbank installiert sind, gibt es für jedes ReLab einen Application-Server, welcher die Kommunikation mit dem Prüfstand übernimmt. Der Hauptserver ist der zentrale Anlaufpunkt und stellt alle Inhalte, die nicht direkt den Prüfstand betreffen zur Verfügung: Internetseiten, Authentifizierung, Webserver und Routing, Firewall, janus-gateway (Videoserver), MySQL Nutzerdantebank, Firewall.

Auf den Applicationservern erfolgen nur die direkten Interaktionen mit dem Versuchsstand (Speicherung von Messdaten, Starten von Bewegungen, Überprüfung von Lösungen) sowie die Erzeugung des RTP-Video-Streams (dieser wird anschließend an janus-gateway gesendet. Die Kommunikation zwischen dem Hauptserver und den Application-Servern teilt sich in die drei Bereiche:

- Routing (Weiterleitung von nginx),
- VideoStream
- und lesenden sowie schreibenden Zugriff auf die MySQL-Nutzerdatenbank auf dem Hauptserver.

Im Fall des Labors Robotki 1 wird die Anwendung auf einem physisch abgetrennten PC ausgeführt und kommuniziert über das Netzwerk mit dem Hauptserver.

## Verwendetes Setup
##### Software

- Webserver: LEMP stack (Linux, nginx, MySQL, Python)
- Videostream: GStreamer

##### Hardware
- PC Dell Optiplex 790
- USB-Webcam Logitech C920 Pro HD
- Yuanda Robotics Yu+ 5/100 Roboter (Kommunikation erfolgt über OPC UA)


_______________________________________________
## Requirements

- Ubuntu (tested with 20.04)
- apt packages:
  - python3 (tested with 3.8.10)
  - python3-venv
  - python3-pip
  - uWSGI (tested with 2.0.19.1): Anwendungsserver für Webanwendungen


##### Python3
Installation Python3, pip und Python Virtual Environment:
```sh
sudo apt update
sudo apt install python3.8.10 python3-pip python3-venv
```

##### uWSGI
Installation und Konfiguration der Bibliothek für den Anwendungsserver uwsgi
```sh
UWSGI_PROFILE_OVERRIDE=ssl=true
pip install uwsgi==2.0.19.1 -I --no-cache-dir
# Verknüpfung, falls nötig, manuell einrichten
sudo ln –s ~/.local/bin/uwsgi /usr/bin/uwsgi
```

##### VideoStream
Video for Linux installieren:
```sh
sudo apt install v4l-utils
```

GStreamer installieren:
```sh
sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio
```

## Installation
##### Git-Repos clonen

Verzeichnis für den Server erstellen:
```sh
mkdir /var/www
```

Die Verzeichnisstruktur sollte nach Durchführung der nachfolgenden Schritte wie folgt aussehen:
```
    /var/www/robotiki
    ├── app
    │   ├── config
    │   ├── db_client               # Verbindung mit Datenbank
    │   └── testbed_communication   # Kommunikation zum Versuchsstand
    ├── autostart                   # Shell-Skripte zum Autostart des Servers
    ├── docs
    ├── vassals                     # Config uswgi vassals
    ├── venv
    └── video
```

Repos clonen:
```sh
cd /var/www
git clone --branch master https://github.com/imesluh/relab-appserver.git robotiki
cd robotiki/app
git clone --branch db_client https://github.com/imesluh/relab-database.git db_client
git clone -- branch opcua https://github.com/imesluh/relab-testbed-comm.git testbed_communication
```

##### Passwörter konfigurieren

Passwort (MySQL Datenbank) in Textdatei schreiben:

```sh
echo <your_password> >> password_db.txt
```

##### Netzwerkadressen konfigurieren

- Videostream:
  - IP Hauptserver und Ports der Streams festlegen in: video/pipeline_vp8.sh
- uWSGI:
  - IP des Applicationserver (falls separater PC) festlegen in .ini-Files im Verzeichnis: vassals
- Pyton:
  - IP-Adresse Hauptserver, Port zur MySQL-Datenbank in app/ReLab.py


##### Python venv konfigurieren

Virtual Environment erstellen:
```sh
cd /var/www/robotiki
python3 -m venv venv
source venv/bin activate
```

pip Pakete installieren:
```sh
(.venv) $ pip install -r requirements.txt
```

ggf. venv deaktivieren:
```sh
(.venv) $ deactivate
```

## Verwendung
Anwendungen in verschiedenen Terminals (oder Alternativen nutzen, z.B. [Terminator](https://wiki.ubuntuusers.de/Terminator/))

1. Videostream starten
GStreamer Pipeline wird mit Webcam als Quelle erstellt und ausgeführt.
```sh
sudo sh /var/www/robotiki/video/pipeline_vp8.sh
```

2. uwsgi Anwendungen (Application Server) starten
```sh
uwsgi --ini uwsgi_relab.ini
```

## Read The Docs Anleitung erstellen
Nach Durchführung aller oben genannten Schritte kann eine html Read The Docs Anleitung mit sphinx erstellt werden. Die venv muss aktiv sein.

```
cd docs
make html
```
Die Anleitung kann über die Datei index.html in einem beliebigen Browser geöffnet werden.
