.. relab-robotiki documentation master file, created by
   sphinx-quickstart on Wed Dec 20 14:19:53 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Willkommen zur ReLab-RobotikI Dokumentation!
==============================================

Dieses Repository enthält den Application Server für das ReLab Labor Robotik I.
Bitte zunächst die allgemeine Dokumentation des Hauptservers lesen.

Beschreibung
-----------------------
Auf den Applicationservern erfolgen nur die direkten Interaktionen mit dem Versuchsstand (Speicherung von Messdaten, Starten von Bewegungen, Überprüfung von Lösungen) sowie die Erzeugung des RTP-Video-Streams (dieser wird anschließend an janus-gateway gesendet. Die Kommunikation zwischen dem Hauptserver und den Application-Servern teilt sich in die drei Bereiche:

- Routing (Weiterleitung von nginx),
- VideoStream
- und lesenden sowie schreibenden Zugriff auf die MySQL-Nutzerdatenbank auf dem Hauptserver.

Im Fall des Labors Robotki 1 wird die Anwendung auf einem physisch abgetrennten PC ausgeführt und kommuniziert über das Netzwerk mit dem Hauptserver.

Verwendetes Setup
--------------------------

Software
^^^^^^^^^
- Webserver: LEMP stack (Linux, nginx, MySQL, Python)
- Videostream: GStreamer

Hardware
^^^^^^^^^
- PC Dell Optiplex 790
- USB-Webcam Logitech C920 Pro HD
- Yuanda Robotics Yu+ 5/100 Roboter (Kommunikation erfolgt über OPC UA)

.. toctree::
   :caption: Einrichtung und Verwendung:
   :titlesonly:

   requirements
   installation
   usage


.. toctree::
   :maxdepth: 4
   :caption: Funktionen:

   modules


Indizes Tabellen
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
