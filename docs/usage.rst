Verwendung
===============

Anwendungen in verschiedenen Terminals (oder Alternativen nutzen, z.B. `Terminator <https://wiki.ubuntuusers.de/Terminator/>`_)

1. Videostream starten

GStreamer Pipeline wird mit Webcam als Quelle erstellt und ausgeführt.

.. code-block:: console

    sudo sh /var/www/robotiki/video/pipeline_vp8.sh


2. uwsgi Anwendungen (Application Server) starten

.. code-block:: console

    uwsgi --ini uwsgi_relab.ini
