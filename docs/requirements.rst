Requirements
===============

- Ubuntu (tested with 20.04)
- apt packages:

  - python3 (tested with 3.8.10)
  - python3-venv
  - python3-pip
  - uWSGI (tested with 2.0.19.1): Anwendungsserver für Webanwendungen


Python3
^^^^^^^^
Installation Python3, pip und Python Virtual Environment:
.. parsed-literal::

    sudo apt update
    sudo apt install python3.8.10 python3-pip python3-venv


uWSGI
^^^^^^^
Installation und Konfiguration der Bibliothek für den Anwendungsserver uwsgi
.. parsed-literal::

    UWSGI_PROFILE_OVERRIDE=ssl=true
    pip install uwsgi==2.0.19.1 -I --no-cache-dir
    # Verknüpfung, falls nötig, manuell einrichten
    sudo ln –s ~/.local/bin/uwsgi /usr/bin/uwsgi

VideoStream
^^^^^^^^^^^^^
Video for Linux installieren:
.. parsed-literal::
    sudo apt install v4l-utils

GStreamer installieren:
.. parsed-literal::
    sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio
