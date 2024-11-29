import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from sps_kommunikation import read_udt_array, UDTFlasche, SPSKommunikation
import subprocess

import uuid


import sqlite3
import struct
import logging

app = Flask(__name__)
app.secret_key = "geheime_schluessel"
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Ordner für Bild-Uploads
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # Max. Dateigröße 2 MB
app.config['SESSION_TYPE'] = 'filesystem'
app.jinja_env.globals.update(enumerate=enumerate)


# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app_debug.log"),  # Speichert Logs in einer Datei
        logging.StreamHandler()  # Zeigt Logs in der Konsole an
    ]
)

#IP aus Datenbank auslesen
def get_sps_settings():
    """Liest die SPS-Einstellungen aus der Datenbank."""
    conn = sqlite3.connect('cocktails.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, value FROM settings WHERE name IN ('sps_ip', 'sps_rack', 'sps_slot')")
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result
def get_sps_ip():
    """Liest die SPS-IP-Adresse aus der settings-Tabelle."""
    try:
        conn = sqlite3.connect('cocktails.db')  # Passe den Datenbanknamen ggf. an
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE name = 'sps_ip'")
        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]  # Gibt die IP-Adresse zurück
        else:
            raise ValueError("SPS-IP-Adresse ist nicht in der Datenbank gespeichert.")
    except sqlite3.Error as e:
        raise RuntimeError(f"Datenbankfehler: {e}")
    

#Benutzerprüfung:
def authenticate_user(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and user['password'] == password:  # Falls Passwörter gehashed sind, verwende `check_password_hash`
        return True
    return False

#Aktuellen Benutzer abrufen:
def get_current_user():
    return session.get('user')


# Funktion zur Verbindung mit der Datenbank
def get_db_connection():
    def trace_callback(sql):
        with open('sql_log.txt', 'a') as f:
            f.write(f"[SQL TRACE]: {sql}\n")
    conn = sqlite3.connect('cocktails.db', timeout=10)
    conn.row_factory = sqlite3.Row
    conn.set_trace_callback(trace_callback)  # Logging aktivieren
    return conn

def log_order(cocktail_id):
    try:
        ip_address = request.remote_addr  # IP-Adresse des Bestellers
        user_agent = request.headers.get('User-Agent')  # User-Agent des Bestellers

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO orders (cocktail_id, ip_address, user_agent)
            VALUES (?, ?, ?)
        ''', (cocktail_id, ip_address, user_agent))
        conn.commit()
        conn.close()
    except Exception as e:
        # Fehlerausgabe bei Problemen
        print(f"Fehler beim Loggen der Bestellung: {e}")
        raise e  # Fehler weiterwerfen, damit `order_cocktail` ihn ebenfalls fängt

# Funktion zum Abrufen der Einstellungen
def get_settings(table):
    conn = get_db_connection()
    cursor = conn.execute(f'SELECT * FROM {table}')
    settings = {row['name']: row['value'] for row in cursor.fetchall()}
    conn.close()
    return settings

# Funktion zum Speichern der Einstellungen
def save_settings(table, settings):
    conn = get_db_connection()
    for name, value in settings.items():
        conn.execute(f'''
            INSERT INTO {table} (name, value) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value=excluded.value
        ''', (name, value))
    conn.commit()
    conn.close()

#Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT username FROM users WHERE username = ?
                ''',
                (username,)
            )
            user = cursor.fetchone()

            if user:
                session['user'] = username
                flash(f'Willkommen zurück, {username}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Benutzername nicht gefunden. Bitte registrieren Sie sich.', 'danger')
                return redirect(url_for('register'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr

        if not username:
            flash('Bitte geben Sie einen gültigen Benutzernamen ein.', 'danger')
            return redirect(url_for('register'))

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Überprüfen, ob ein Benutzer mit denselben Daten bereits existiert
            cursor.execute(
                '''
                SELECT id FROM users WHERE user_agent = ? OR ip_address = ?
                ''',
                (user_agent, ip_address)
            )
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Ein Benutzer mit diesem Gerät existiert bereits. Bitte melden Sie sich an.', 'warning')
                return redirect(url_for('login'))

            # Neuen Benutzer erstellen
            cursor.execute(
                '''
                INSERT INTO users (username, user_agent, ip_address)
                VALUES (?, ?, ?)
                ''',
                (username, user_agent, ip_address)
            )
            conn.commit()

            # Benutzer in die Session setzen
            session['user'] = username
            flash(f'Willkommen, {username}! Sie wurden erfolgreich registriert.', 'success')
            return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Erfolgreich ausgeloggt.', 'success')
    # Weiterleitung zur Hauptseite (index)
    return redirect(url_for('index'))


@app.route('/order_logs', methods=['GET'])
def order_logs():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Bestellungen mit Cocktailnamen abrufen
            cursor.execute('''
                SELECT 
                    orders.id, 
                    orders.cocktail_id, 
                    cocktails.name AS cocktail_name,
                    users.username, 
                    orders.order_time, 
                    orders.ip_address, 
                    orders.user_agent
                FROM orders
                LEFT JOIN cocktails ON orders.cocktail_id = cocktails.id
                LEFT JOIN users ON orders.user_id = users.id
                ORDER BY orders.order_time DESC
            ''')
            orders = cursor.fetchall()
        return render_template('order_logs.html', orders=orders)
    except Exception as e:
        logging.error(f"Fehler beim Abrufen des Bestellungsprotokolls: {e}")
        flash("Fehler beim Laden des Protokolls.", "danger")
        return redirect(url_for('index'))



#Flaschen Laden / Cocktailerstellen
@app.route('/create_cocktail', methods=['GET', 'POST'])
def create_cocktail():
    sps = SPSKommunikation(get_sps_ip())
    flaschen = read_udt_array(sps, 120, 0, 38, 30)  # Flaschen aus der SPS laden

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if request.method == 'POST':
            try:
                # Formulardaten abrufen
                name = request.form['name']
                description = request.form.get('description', '')
                ingredients_text = request.form.get('ingredients', '')

                # Bild hochladen und Pfad speichern
                image_path = None
                if 'image' in request.files:
                    image = request.files['image']
                    if image.filename:  # Überprüfen, ob eine Datei ausgewählt wurde
                        upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                        os.makedirs(upload_folder, exist_ok=True)  # Sicherstellen, dass der Ordner existiert
                        filename = secure_filename(image.filename)
                        absolute_path = os.path.join(upload_folder, filename)
                        image.save(absolute_path)  # Bild speichern
                        # Speichere den relativen Pfad für die Datenbank
                        image_path = f"uploads/{filename}"
                        logging.info(f"Bild gespeichert unter: {image_path}")

                # Cocktail in die Datenbank einfügen
                cursor.execute(
                    '''
                    INSERT INTO cocktails (name, description, ingredients, image_path)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (name, description, ingredients_text, image_path)
                )
                cocktail_id = cursor.lastrowid
                logging.info(f"Cocktail {name} mit ID {cocktail_id} wurde erstellt. Bildpfad: {image_path}")

                # Zutaten in die Datenbank einfügen
                for i, flasche in enumerate(flaschen, start=1):
                    flasche_name = flasche.name.strip()
                    menge = request.form.get(f'menge_{i}', '0').strip()

                    # Validierung der Menge
                    if not menge.isdigit():
                        menge = 0
                    menge = int(menge)

                    # Nur Flaschen mit Namen und gültigen Mengen speichern
                    if flasche_name and menge > 0:
                        cursor.execute(
                            '''
                            INSERT INTO cocktail_ingredients (cocktail_id, flasche_name, menge_ml)
                            VALUES (?, ?, ?)
                            ON CONFLICT(cocktail_id, flasche_name) DO UPDATE SET menge_ml = excluded.menge_ml
                            ''',
                            (cocktail_id, flasche_name, menge)
                        )

                conn.commit()

                # Weiterleitung zur Hauptseite
                return redirect(url_for('index'))

            except Exception as e:
                logging.error(f"Fehler beim Erstellen eines Cocktails: {e}")
                flash(f"Fehler: {e}", "danger")

    return render_template('create_cocktail.html', flaschen=flaschen)


#Einstellungen
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('user') not in ['Hölker', 'Schülting']:
        flash("Zugriff verweigert. Nur Hölker oder Schülting dürfen die Einstellungen ändern.", "danger")
        return redirect(url_for('index'))

    with sqlite3.connect('cocktails.db') as conn:
        cursor = conn.cursor()

        if request.method == 'POST':
            # Neue SPS-IP aus dem Formular abrufen
            sps_ip = request.form.get('sps_ip')
            global_cocktail_access = '1' if 'global_cocktail_access' in request.form else '0'

            # SPS-IP speichern
            if sps_ip:
                try:
                    cursor.execute('''
                        UPDATE settings SET value = ? WHERE name = 'sps_ip'
                    ''', (sps_ip,))
                except sqlite3.Error as e:
                    flash(f"Fehler beim Speichern der SPS-IP: {e}", "danger")
                else:
                    flash("SPS-IP erfolgreich gespeichert.", "success")

            # Globale Cocktail-Erstellung speichern
            try:
                cursor.execute('''
                    INSERT INTO settings (name, value) VALUES ('global_cocktail_access', ?)
                    ON CONFLICT(name) DO UPDATE SET value = excluded.value
                ''', (global_cocktail_access,))
            except sqlite3.Error as e:
                flash(f"Fehler beim Speichern der globalen Zugriffseinstellung: {e}", "danger")
            else:
                flash("Zugriffseinstellung erfolgreich gespeichert.", "success")

        # Aktuelle Einstellungen laden
        cursor.execute('SELECT value FROM settings WHERE name = "sps_ip"')
        sps_ip = cursor.fetchone()
        sps_ip = sps_ip[0] if sps_ip else "192.168.0.1"  # Fallback auf Standardwert

        cursor.execute('SELECT value FROM settings WHERE name = "global_cocktail_access"')
        global_access = cursor.fetchone()
        global_access = global_access[0] == '1' if global_access else False

    return render_template('settings.html', sps_ip=sps_ip, global_access=global_access)

# Route zum Speichern der WLAN-Konfiguration
@app.route('/save_wifi_config', methods=['POST'])
def save_wifi_config():
    ssid = request.form['ssid']
    password = request.form['password']
    logging.info(f"SSID: {ssid} erfolgreich empfangen.")
    logging.info(f"Password: {password} erfolgreich empfangen.")
    try:
        # Ausführung des nmcli-Befehls
        result = subprocess.run(
            ['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logging.info(f"WLAN-Verbindung erfolgreich hergestellt: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        # Fehler bei der Ausführung des Befehls
        error_message = e.stderr.strip()
        logging.error(f"Fehler beim Verbinden mit dem WLAN: {error_message}")
    except Exception as e:
        logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {str(e)}")
    
    # Statt `flash`, einfach Logging verwenden
    return redirect(url_for('settings'))

@app.context_processor
def inject_global_settings():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE name = ?', ('global_cocktail_access',))
        global_access = cursor.fetchone()
        global_access = global_access['value'] == '1' if global_access else False
    return dict(global_access=global_access)

@app.route('/basic_settings', methods=['GET', 'POST'])
def basic_settings():
    if request.method == 'POST':
        # Speichern der Grundeinstellungen
        basic_settings_data = {
            'basic_setting1': request.form['basic_setting1'],
            'basic_setting2': request.form['basic_setting2']
        }
        save_settings('basic_settings', basic_settings_data)
        flash("Grundeinstellungen erfolgreich gespeichert!", "success")
        return redirect(url_for('basic_settings'))

    # Laden der vorhandenen Grundeinstellungen für das Template
    basic_settings = get_settings('basic_settings')
    print("Geladene Grundeinstellungen:", basic_settings)  # Debugging-Ausgabe
    return render_template('basic_settings.html', basic_settings=basic_settings)

#Order Queue
@app.route('/order_queue', methods=['GET'])
def order_queue():
    try:
        sps = SPSKommunikation(get_sps_ip())
        orders = []

        for i in range(50):  # Es gibt 50 Cocktails in der SPS
            start_address = i * 62  # Jeder Cocktail ist 62 Bytes entfernt
            raw_data = sps.read_db(130, start_address, 22)  # Nur den Namen lesen (22 Bytes)
            max_length, actual_length, name_raw = struct.unpack('>BB20s', raw_data)
            cocktail_name = name_raw[:actual_length].decode('ascii').strip()

            if cocktail_name:  # Nur nicht-leere Namen in die Liste aufnehmen
                orders.append({"name": cocktail_name, "sps_index": i + 1})

        sps.disconnect()

        return render_template('order_queue.html', orders=orders)
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Warteschleife: {e}")
        flash("Fehler beim Abrufen der Warteschleife.", "danger")
        return redirect(url_for('index'))


#delete Order
@app.route('/delete_order/<int:order_index>', methods=['POST'])
def delete_order(order_index):
    try:
        sps = SPSKommunikation(get_sps_ip())
        logging.info(f"Order Index: {order_index}")
        
        # Berechnung der Adressen und Rücksetzung
        start_address_name = (order_index) * 62
        start_address_menge = start_address_name + 22
        empty_name = struct.pack('>BB20s', 20, 0, b'')
        zero_menge = struct.pack('>20H', *[0] * 20)
        sps.write_db(130, start_address_name, empty_name)
        sps.write_db(130, start_address_menge, zero_menge)
        
        # Überprüfung
        read_name = sps.read_db(130, start_address_name, 22)
        _, actual_length, read_name_raw = struct.unpack('>BB20s', read_name)
        read_name_decoded = read_name_raw[:actual_length].decode('ascii').strip()
        read_menge = sps.read_db(130, start_address_menge, 40)
        read_menge_values = struct.unpack('>20H', read_menge)

        if read_name_decoded != '' or any(value != 0 for value in read_menge_values):
            raise ValueError("Löschen nicht erfolgreich.")

        logging.info(f"Bestellung an SPS-Index {order_index} erfolgreich gelöscht.")
        sps.disconnect()

        # Echtzeitsignal senden
        socketio.emit('order_updated', {'message': 'Order list updated'})

        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Fehler beim Löschen der Bestellung: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

#set Referenzieren Bit
@app.route('/set_sps_bit', methods=['POST'])
def set_sps_bit():
    try:
        logging.info("Verbindung zur SPS wird hergestellt...")
        sps = SPSKommunikation(get_sps_ip())
        
        # SPS-Bit setzen
        db_number = 100
        byte_index = 1  # Byte-Offset in der DB
        bit_index = 0   # Bit im Byte
        logging.info(f"Setze Bit {bit_index} in DB {db_number}, Byte {byte_index}...")
        
        # Bit setzen
        sps.set_bit(db_number, byte_index, bit_index, True)
        logging.info("Bit erfolgreich gesetzt.")
        
        sps.disconnect()
        logging.info("Verbindung zur SPS getrennt.")
        
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Fehler beim Setzen des Bits: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

#Toggle Reglerfreigabe
@app.route('/toggle_reglerfreigabe', methods=['POST'])
def toggle_reglerfreigabe():
    try:
        # Verbindung zur SPS herstellen
        sps = SPSKommunikation(get_sps_ip())
        logging.info("Reglerfreigabe angefordert")
        
        # Aktuellen Wert des Bits auslesen
        db_number = 100
        byte_index = 1
        bit_index = 1
        current_byte = sps.read_db(db_number, byte_index, 1)[0]
        current_bit = (current_byte >> bit_index) & 1
        logging.info(f"Status Reglerfreigabe:{current_bit}")
        # Bit invertieren
        new_bit = 0 if current_bit else 1
        new_byte = (current_byte & ~(1 << bit_index)) | (new_bit << bit_index)
        
        # Neuen Byte-Wert in die SPS schreiben
        sps.write_db(db_number, byte_index, bytes([new_byte]))
        logging.info(f"Reglerfreigabe umgeschaltet. Neuer Wert: {new_bit}")
        
        sps.disconnect()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Fehler beim Umschalten der Reglerfreigabe: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

#Glas Entnommen
@app.route("/glas_entnommen", methods=["POST"])
def glas_entnommen():
    try:
        sps = SPSKommunikation(get_sps_ip())  # Hole die SPS-IP aus der Datenbank
        db_number = 130
        start_address = 0  # Startadresse für den String
        string_data = struct.pack(">BB20s", 20, 0, b"")  # STRING[20] auf '' setzen
        
        sps.write_db(db_number, start_address, string_data)
                # SPS-Bit setzen
        #db_number = 100
        #byte_index = 1  # Byte-Offset in der DB
        #bit_index = 3   # Bit im Byte
        #logging.info(f"Setze Bit {bit_index} in DB {db_number}, Byte {byte_index}...")
        
        # Bit setzen
        #sps.set_bit(db_number, byte_index, bit_index, True)
        #logging.info("Bit erfolgreich gesetzt.")
        sps.disconnect()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Fehler beim Zurücksetzen des Strings: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

#Flaschen
@app.route('/flaschen_alle', methods=['GET', 'POST'])
def flaschen_alle():
    db_number = 120
    array_start = 0
    udt_size = 38
    array_length = 30
    logging.debug(f"Test falsches Skript?")

    try:
        print("Initialisiere Verbindung zur SPS...")
        sps = SPSKommunikation(get_sps_ip())
        print(f"Verbindung zur SPS erfolgreich: {sps.ip}")
    except Exception as e:
        print(f"Fehler beim Verbinden zur SPS: {e}")
        flash("Verbindung zur SPS fehlgeschlagen.", "danger")
        return render_template('flaschen_alle.html', flaschen=[])

    # POST: Speichern der Änderungen
    if request.method == 'POST':
        try:
            # Verbindung zur SQLite-Datenbank herstellen
            conn = sqlite3.connect('cocktails.db')
            cursor = conn.cursor()

            # Tabelle `flaschen` erstellen, falls sie nicht existiert
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flaschen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    alkoholgehalt REAL NOT NULL
                )
            ''')

            # Liste der aktuellen Flaschen aus der SPS
            current_flasks = set()

            # Iteriere über die Flaschen und verarbeite sie
            for i in range(1, array_length + 1):
                print(f"Verarbeite Änderungen für Flasche {i}...")

                # Formulardaten auslesen
                flasche_name = request.form[f'name_{i}'].strip()
                if not flasche_name:  # Überspringe leere Flaschen
                    logging.warning(f"Flasche {i} hat keinen Namen, überspringe...")
                    continue

                current_flasks.add(flasche_name)

                flasche_x = float(request.form[f'x_{i}'])
                flasche_y = float(request.form[f'y_{i}'])
                dosier_art = bool(request.form.get(f'dosier_art_{i}', 'off') == 'on')
                dosiermenge = int(request.form[f'dosiermenge_{i}'])
                alkoholgehalt = float(request.form[f'alkoholgehalt_{i}'])

                # Logging der eingelesenen Formulardaten
                logging.debug(f"Formular-Daten für Flasche {i}: Name={flasche_name}, X={flasche_x}, Y={flasche_y}, Dosierart={dosier_art}, Dosiermenge={dosiermenge}, Alkoholgehalt={alkoholgehalt}")

                flasche = UDTFlasche(
                    name=flasche_name,
                    x=flasche_x,
                    y=flasche_y,
                    dosier_art=dosier_art,
                    dosiermenge=dosiermenge,
                    alkoholgehalt=alkoholgehalt
                )

                # In die SPS schreiben
                sps.write_flasche(db_number=db_number, index=i, flasche=flasche, udt_size=udt_size)
                logging.info(f"Flasche {i} erfolgreich in die SPS geschrieben.")

                # Daten in die SQLite-Datenbank einfügen oder aktualisieren
                try:
                    cursor.execute(
                        '''
                        INSERT INTO flaschen (name, alkoholgehalt) 
                        VALUES (?, ?)
                        ON CONFLICT(name) DO UPDATE SET alkoholgehalt=excluded.alkoholgehalt
                        ''',
                        (flasche.name, flasche.alkoholgehalt)
                    )
                except sqlite3.IntegrityError as e:
                    logging.error(f"Fehler beim Einfügen/Aktualisieren von Flasche '{flasche.name}': {e}")

            # Entferne alle Zutaten aus `cocktail_ingredients`, die nicht mehr existieren
            cursor.execute('SELECT name FROM flaschen')
            existing_flasks = set(row[0] for row in cursor.fetchall())

            flasks_to_remove = existing_flasks - current_flasks
            if flasks_to_remove:
                logging.info(f"Entferne Zutaten für nicht mehr existierende Flaschen: {flasks_to_remove}")
                for flask in flasks_to_remove:
                    cursor.execute('DELETE FROM cocktail_ingredients WHERE flasche_name = ?', (flask,))
                    logging.info(f"Zutaten mit Flasche '{flask}' wurden entfernt.")

            # Änderungen in der SQLite-Datenbank speichern
            conn.commit()
            flash("Änderungen erfolgreich gespeichert.", "success")
        except Exception as e:
            logging.error(f"Fehler beim Speichern: {e}")
            flash(f"Fehler beim Speichern der Flaschen: {e}", "danger")
        finally:
            sps.disconnect()
            conn.close()
            return redirect(url_for('flaschen_alle'))

    # GET: Flaschen laden
    try:
        print("Lese Flaschen aus der SPS...")
        flaschen = read_udt_array(sps, db_number, array_start, udt_size, array_length)
        print(f"Flaschen geladen: {len(flaschen)}")
        
        # Daten in die SQLite-Datenbank einfügen oder aktualisieren
        with get_db_connection() as conn:
            cursor = conn.cursor()

            for flasche in flaschen:
                flasche_name = flasche.name
                alkoholgehalt = flasche.alkoholgehalt

                if not flasche_name:  # Überspringe Flaschen ohne Namen
                    logging.warning(f"Flasche hat keinen Namen, überspringe...")
                    continue

                # Prüfen, ob die Flasche bereits existiert
                cursor.execute('SELECT COUNT(*) FROM flaschen WHERE name = ?', (flasche_name,))
                exists = cursor.fetchone()[0]

                if not exists:
                    # Füge neue Flasche hinzu
                    logging.info(f"Füge Flasche '{flasche_name}' mit Alkoholgehalt {alkoholgehalt}% hinzu.")
                    cursor.execute(
                        '''
                        INSERT INTO flaschen (name, alkoholgehalt)
                        VALUES (?, ?)
                        ''',
                        (flasche_name, alkoholgehalt)
                    )
                    conn.commit()
                    logging.info(f"Flasche '{flasche_name}' zur Datenbank hinzugefügt.")
                else:
                    logging.info(f"Flasche '{flasche_name}' existiert bereits, überspringe.")
            conn.commit()

    except Exception as e:
        logging.error(f"Fehler beim Laden und Einfügen der Flaschen in die Datenbank: {e}")
        flash(f"Fehler beim Laden der Flaschen aus der SPS: {e}", "danger")
        flaschen = []

    finally:
        sps.disconnect()

    return render_template('flaschen_alle.html', flaschen=flaschen)





@app.route('/order_cocktail/<int:id>', methods=['POST'])
def order_cocktail(id):
    try:
        # Verbindung zur SPS herstellen
        sps = SPSKommunikation(get_sps_ip())

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Cocktail-Daten abrufen
            cursor.execute('SELECT name, counter FROM cocktails WHERE id = ?', (id,))
            cocktail_row = cursor.fetchone()

            if not cocktail_row:
                return jsonify({"success": False, "error": "Cocktail nicht gefunden"}), 404

            cocktail_name = cocktail_row['name']
            current_counter = cocktail_row['counter']

            # Zutaten und Mengen für den Cocktail laden
            cursor.execute('SELECT flasche_name, menge_ml FROM cocktail_ingredients WHERE cocktail_id = ?', (id,))
            ingredients = cursor.fetchall()

            # Benutzername aus der Session abrufen
            username = session.get('user')
            if not username:
                return jsonify({"success": False, "error": "Benutzer nicht eingeloggt"}), 403

            # Benutzer-ID abrufen
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            user_id = user['id'] if user else None

            if not user_id:
                return jsonify({"success": False, "error": "Benutzer-ID nicht gefunden"}), 404

            # Alkoholgehalt berechnen
            alcohol_content = 0.0
            for ingredient in ingredients:
                flasche_name, menge = ingredient
                cursor.execute('SELECT alkoholgehalt FROM flaschen WHERE name = ?', (flasche_name,))
                alkoholgehalt_row = cursor.fetchone()
                if alkoholgehalt_row:
                    alkoholgehalt = alkoholgehalt_row[0]
                    alcohol_content += (menge * alkoholgehalt / 100)  # Alkoholgehalt in ml berechnen
                    logging.debug(f"Berechne Alkoholgehalt: Zutat {flasche_name}, Menge {menge} ml, Alkoholgehalt {alkoholgehalt}%")
            logging.debug(f"Berechne Alkoholgehalt Gesamt {alcohol_content}%")

            # Bestellung in die Tabelle `orders` eintragen
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')
            cursor.execute(
                '''
                INSERT INTO orders (cocktail_id, ip_address, user_agent, user_id, alcohol_content)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (id, ip_address, user_agent, user_id, round(alcohol_content, 2))
            )

            # Bestellung in `user_orders` eintragen
            cursor.execute(
                '''
                INSERT INTO user_orders (user_id, cocktail_id, order_time, alcohol_content)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                ''',
                (user_id, id, round(alcohol_content, 2))
            )

            # Zähler für den Cocktail um 1 erhöhen
            cursor.execute(
                'UPDATE cocktails SET counter = counter + 1 WHERE id = ?',
                (id,)
            )
            logging.info(f"Zähler für Cocktail {id} inkrementiert. Alter Wert: {current_counter}")

            conn.commit()

        # Initialisiere das Array der Mengen
        menge_array = [0] * 20

        # STRING-Daten mit Längenangabe für die SPS vorbereiten
        max_length = 20  # Maximale Länge des Strings
        actual_length = len(cocktail_name)
        if actual_length > max_length:
            cocktail_name = cocktail_name[:max_length]  # Kürzen auf maximale Länge
        string_data = bytes([max_length, actual_length]) + cocktail_name.ljust(max_length).encode('ascii')

        # Zutaten und Mengen in die korrekten Indizes schreiben
        for ingredient in ingredients:
            flasche_name = ingredient['flasche_name']
            menge = int(ingredient['menge_ml'])

            # Index der Flasche herausfinden
            flaschen_index = next(
                (i for i, flasche in enumerate(read_udt_array(sps, 120, 0, 38, 30)) if flasche.name == flasche_name), None
            )

            if flaschen_index is not None and flaschen_index < len(menge_array):
                menge_array[flaschen_index] = menge

        # Daten in die SPS schreiben
        db_number = 130
        sps.write_db(db_number, 3038, string_data)  # Name des Cocktails
        for i, menge in enumerate(menge_array):
            sps.write_db(db_number, 3060 + (i * 2), struct.pack('>H', menge))  # Mengen (als UInt)

        # DB100 dbx1.4 setzen
        db_number_control = 100
        byte_index = 1
        bit_index = 4
        logging.info(f"Setze DB{db_number_control}.DBX{byte_index}.{bit_index}")
        sps.set_bit(db_number_control, byte_index, bit_index, True)
        logging.info(f"Bit DB{db_number_control}.DBX{byte_index}.{bit_index} erfolgreich gesetzt.")

        sps.disconnect()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Fehler bei der Bestellung: {e}")
        return jsonify({"success": False, "error": str(e)}), 500





#
@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Benutzerliste abrufen
            cursor.execute('SELECT id, username FROM users')
            users = cursor.fetchall()

            # Daten für den Graphen abrufen
            cursor.execute('''
                SELECT user_id, order_time, COUNT(*) as cocktail_count, SUM(alcohol_content) as total_alcohol
                FROM user_orders
                GROUP BY user_id, DATE(order_time)
                ORDER BY order_time
            ''')
            orders = cursor.fetchall()

            # Daten für den aktuellen Tag abrufen
            cursor.execute('''
                SELECT user_id, COUNT(*) as cocktail_count, SUM(alcohol_content) as total_alcohol
                FROM user_orders
                WHERE DATE(order_time) = DATE('now')
                GROUP BY user_id
            ''')
            today_orders = cursor.fetchall()

        # Benutzer- und Bestellungsdaten aufbereiten
        users_list = [{'id': user[0], 'username': user[1]} for user in users]
        orders_list = [
            {
                'user_id': order[0],
                'order_time': order[1],
                'cocktail_count': order[2],
                'total_alcohol': order[3]
            }
            for order in orders
        ]
        today_orders_dict = {order[0]: {'cocktail_count': order[1], 'total_alcohol': order[2]} for order in today_orders}

        # Gesamtdaten berechnen
        total_cocktails = sum(order['cocktail_count'] for order in orders_list)
        total_cocktails_today = sum(order['cocktail_count'] for order in today_orders)
        total_alcohol_today = sum(order['total_alcohol'] for order in today_orders)

        return render_template(
            'dashboard.html',
            users=users_list,
            orders=orders_list,
            total_cocktails=total_cocktails,
            total_cocktails_today=total_cocktails_today,
            total_alcohol_today=total_alcohol_today,
            today_orders=today_orders_dict
        )

    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Dashboard-Daten: {e}", exc_info=True)
        flash("Fehler beim Laden des Dashboards.", "danger")
        return redirect(url_for('index'))





@app.route('/reset_counter/<int:id>', methods=['POST'])
def reset_counter(id):
    # Überprüfen, ob ein Benutzer eingeloggt ist
    if not session.get('user'):
        return jsonify({"success": False, "error": "Nicht autorisiert"}), 403

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Zähler zurücksetzen
        cursor.execute('UPDATE cocktails SET counter = 0 WHERE id = ?', (id,))
        conn.commit()

    return jsonify({"success": True})   

# Route für die Hauptseite (Cocktailauswahl), sortiert nach dem höchsten Zählerwert
@app.route('/')
def index():
    user_agent = request.headers.get('User-Agent')
    ip_address = request.remote_addr

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT username FROM users WHERE user_agent = ? OR ip_address = ?
            ''',
            (user_agent, ip_address)
        )
        user = cursor.fetchone()

        if user:
            session['user'] = user['username']  # Benutzer erkannt, in die Session setzen
        else:
            return redirect(url_for('register'))  # Benutzer nicht erkannt, zur Registrierung leiten

    # Weiter mit der Hauptseite
    cocktails = cursor.execute('SELECT * FROM cocktails ORDER BY counter DESC').fetchall()
    return render_template('index.html', cocktails=cocktails)

# Route zum Bearbeiten eines existierenden Cocktails
@app.route('/edit_cocktail/<int:id>', methods=['GET', 'POST'])
def edit_cocktail(id):
    sps = SPSKommunikation(get_sps_ip())
    flaschen = read_udt_array(sps, 120, 0, 38, 30)  # Flaschen aus der SPS laden

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if request.method == 'POST':
            # Formulardaten abrufen
            name = request.form['name']
            description = request.form.get('description', '')

            # Bild-Upload verarbeiten
            image_path = None
            if 'image' in request.files:
                image = request.files['image']
                if image.filename:  # Nur speichern, wenn ein neues Bild hochgeladen wurde
                    upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    filename = secure_filename(image.filename)
                    new_image_path = os.path.join(upload_folder, filename)
                    image.save(new_image_path)

                    # Alten Bildpfad abrufen, um die alte Datei zu löschen
                    cursor.execute('SELECT image_path FROM cocktails WHERE id = ?', (id,))
                    old_image = cursor.fetchone()['image_path']

                    # Altes Bild löschen, falls es existiert
                    if old_image and os.path.exists(os.path.join('static', old_image)):
                        os.remove(os.path.join('static', old_image))

                    # Relativen Pfad für die Datenbank speichern
                    image_path = f"uploads/{filename}"

            # Zutaten aktualisieren oder einfügen
            ingredients = []
            for i, flasche in enumerate(flaschen, start=1):
                menge = request.form.get(f'menge_{i}', '0').strip()

                # Validierung der Menge
                if not menge.isdigit():
                    menge = 0
                menge = int(menge)

                if menge > 0:  # Nur Flaschen mit gültigen Mengen speichern
                    ingredients.append((flasche.name.strip(), menge))

            # Cocktail-Daten aktualisieren
            if image_path:
                cursor.execute(
                    '''
                    UPDATE cocktails
                    SET name = ?, description = ?, image_path = ?
                    WHERE id = ?
                    ''',
                    (name, description, image_path, id)
                )
            else:
                cursor.execute(
                    '''
                    UPDATE cocktails
                    SET name = ?, description = ?
                    WHERE id = ?
                    ''',
                    (name, description, id)
                )

            # Zutaten speichern
            # Vor der Schleife: Alle Einträge zur "id" entfernen
            #cursor.execute('DELETE FROM cocktail_ingredients WHERE cocktail_id = ?', (id,))
            #logging.info(f"Bestehende Zutaten für Cocktail-ID {id} wurden entfernt.")
            for flasche_name, menge in ingredients:
                cursor.execute(
                    '''
                    INSERT INTO cocktail_ingredients (cocktail_id, flasche_name, menge_ml)
                    VALUES (?, ?, ?)
                    ON CONFLICT(cocktail_id, flasche_name) DO UPDATE SET menge_ml = excluded.menge_ml
                    ''',
                    (id, flasche_name, menge)
                )
            conn.commit()
            logging.info(f"Cocktail-ID {id} wurde bearbeitet.")

            # Weiterleitung zur Hauptseite
            return redirect(url_for('index'))

        # Daten für das Bearbeitungsformular laden
        cursor.execute('SELECT * FROM cocktails WHERE id = ?', (id,))
        cocktail = dict(cursor.fetchone())

        cursor.execute('SELECT flasche_name, menge_ml FROM cocktail_ingredients WHERE cocktail_id = ?', (id,))
        saved_ingredients = {row['flasche_name']: row['menge_ml'] for row in cursor.fetchall()}

        # Flaschen mit gespeicherten Werten kombinieren (Positionen aus der SPS nutzen)
        for flasche in flaschen:
            flasche.menge = saved_ingredients.get(flasche.name.strip(), '')  # Vorbelegen oder leer lassen

    return render_template('edit_cocktail.html', cocktail=cocktail, flaschen=flaschen)

@app.route('/delete_cocktail/<int:id>', methods=['POST'])
def delete_cocktail(id):
    try:
            # Überprüfen, ob ein Benutzer eingeloggt ist
        if not session.get('user'):
            return jsonify({"success": False, "error": "Nicht autorisiert"}), 403

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Cocktail löschen
            cursor.execute('DELETE FROM cocktails WHERE id = ?', (id,))
            cursor.execute('DELETE FROM cocktail_ingredients WHERE cocktail_id = ?', (id,))
            conn.commit()

        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Fehler beim Löschen des Cocktails {id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/remove_image_path/<int:id>', methods=['POST'])
def remove_image_path(id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cocktail = cursor.execute('SELECT * FROM cocktails WHERE id = ?', (id,)).fetchone()

        if cocktail is None:
            return jsonify({"error": "Cocktail mit dieser ID existiert nicht."}), 404

        try:
            # Bildpfad in der Datenbank auf NULL setzen
            cursor.execute('UPDATE cocktails SET image_path = NULL WHERE id = ?', (id,))
            conn.commit()
            return jsonify({"success": True})  # Erfolgsantwort als JSON zurückgeben

        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "error": str(e)}), 500


# Flask-Anwendung starten
if __name__ == "__main__":
    print("Starte Flask-Anwendung...")
    #app.run(debug=True, host='0.0.0.0', port=5000)
    socketio = SocketIO(app, cors_allowed_origins="*")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)