# Anleitung: Flask-App auf Raspberry Pi automatisch starten und bei Absturz neustarten

Diese Anleitung beschreibt, wie du eine Flask-App (`app.py`) auf einem Raspberry Pi so einrichtest, dass sie:

1. Automatisch beim Hochfahren gestartet wird.
2. Bei einem Absturz automatisch neu gestartet wird.

---

## Voraussetzungen

- Raspberry Pi mit Raspberry Pi OS (oder einem ähnlichen Linux-Betriebssystem).
- Python3, PIP und Flask sind installiert.
- Die Flask-App `app.py` befindet sich an einem festen Speicherort, z. B. `/home/pi/app/Alkinator/Alkinator App/app.py`.
- git muss installiert sein.
---

## Schritte

### 1. Systemd-Dienstdatei erstellen

Erstelle eine Systemd-Dienstdatei, die die Flask-App verwaltet:

1. Öffne den Texteditor:
   ```bash
   sudo nano /etc/systemd/system/app.service

[Unit]
Description=Flask App
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/app/app.py
WorkingDirectory=/home/pi/app/
Restart=always
RestartSec=5
User=pi
Environment=FLASK_APP=app.py FLASK_ENV=production

[Install]
WantedBy=multi-user.target


Parameterbeschreibung:

ExecStart: Pfad zu Python3 und zur Flask-App.
WorkingDirectory: Verzeichnis, in dem sich die app.py befindet.
Restart=always: Neustart bei Absturz.
RestartSec=5: 5 Sekunden Verzögerung vor einem Neustart.
User=pi: Der Benutzer, der den Dienst ausführt.


Systemd-Konfiguration neu laden:
sudo systemctl daemon-reload

Dienst für den automatischen Start aktivieren:
sudo systemctl enable app.service

Dienst starten:
sudo systemctl start app.service

Status des Dienstes überprüfen:
sudo systemctl status app.service



Logs und Fehleranalyse
journalctl -u app.service


Gunicorn installieren:
pip install gunicorn


Systemd-Dienstdatei anpassen: Ersetze in der Datei /etc/systemd/system/app.service die Zeile ExecStart durch:
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:80 app:app


Systemd neu laden und Dienst neustarten:
sudo systemctl daemon-reload
sudo systemctl restart app.service


Debugging
Überprüfe den Status des Dienstes:
sudo systemctl status app.service

Zeige die Logs an:
journalctl -u app.service
