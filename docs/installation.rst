Installation
===============


Git-Repos clonen
^^^^^^^^^^^^^^^^^

Verzeichnis für den Server erstellen:

.. code-block:: console

    mkdir /var/www

Die Verzeichnisstruktur sollte nach Durchführung der nachfolgenden Schritte wie folgt aussehen:

.. parsed-literal::

    /var/www/robotiki
    ├── app
    │   ├── config
    │   ├── db_client               # Verbindung mit Datenbank
    │   └── testbed_communication   # Kommunikation zum Versuchsstand
    ├── autostart                   # Shell-Skripte zum Autostart des Servers
    ├── docs
    ├── vassals                     # Config uswgi vassals
    ├── venv
    └── video


Repos clonen:

.. code-block:: console

    cd /var/www
    git clone --branch master https://github.com/imesluh/relab-appserver.git robotiki
    cd robotiki/app
    git clone --branch db_client https://github.com/imesluh/relab-database.git db_client
    git clone -- branch opcua https://github.com/imesluh/relab-testbed-comm.git testbed_communication


Passwörter konfigurieren
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Passwort (MySQL Datenbank) in Textdatei schreiben:

.. code-block:: console

    echo <your_password> >> password_db.txt

Netzwerkadressen konfigurieren
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- Videostream:

  - IP Hauptserver und Ports der Streams festlegen in: video/pipeline_vp8.sh

- uWSGI:

  - IP des Applicationserver (falls separater PC) festlegen in .ini-Files im Verzeichnis: vassals

- Pyton:

  - IP-Adresse Hauptserver, Port zur MySQL-Datenbank in app/ReLab.py


Python venv konfigurieren
^^^^^^^^^^^^^^^^^^^^^^^^^
Virtual Environment erstellen:

.. code-block:: console

    cd /var/www/robotiki
    python3 -m venv venv
    source venv/bin activate

pip Pakete installieren:

.. code-block:: console

   (.venv) $ pip install -r requirements.txt


ggf. venv deaktivieren:

.. code-block:: console

    (.venv) $ deactivate
