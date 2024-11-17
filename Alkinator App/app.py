import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from sps_kommunikation import read_udt_array, UDTFlasche, SPSKommunikation

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
    filename='app_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
        username = request.form['username']
        password = request.form['password']

        if authenticate_user(username, password):
            session['user'] = username
            flash('Erfolgreich eingeloggt!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Ungültiger Benutzername oder Passwort.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Erfolgreich ausgeloggt.', 'success')
    # Weiterleitung zur Hauptseite (index)
    return redirect(url_for('index'))

@app.route('/order_logs')
def order_logs():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Bestellungen aus der `orders`-Tabelle abrufen
        cursor.execute('SELECT * FROM orders ORDER BY order_time DESC')
        orders = [dict(row) for row in cursor.fetchall()]

    return render_template('order_logs.html', orders=orders)



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
    if request.method == 'POST':
        # Neue SPS-IP aus dem Formular abrufen
        sps_ip = request.form.get('sps_ip')

        if sps_ip:
            try:
                # Verbindung zur Datenbank herstellen
                conn = sqlite3.connect('cocktails.db')
                cursor = conn.cursor()

                # SPS-IP in der Datenbank aktualisieren
                cursor.execute('''
                    UPDATE settings SET value = ? WHERE name = 'sps_ip'
                ''', (sps_ip,))
                conn.commit()
                conn.close()

                flash("SPS-IP erfolgreich gespeichert.", "success")
            except sqlite3.Error as e:
                flash(f"Fehler beim Speichern der SPS-IP: {e}", "danger")
        else:
            flash("Bitte eine gültige SPS-IP eingeben.", "warning")

    # Aktuelle SPS-IP aus der Datenbank laden
    conn = sqlite3.connect('cocktails.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE name = "sps_ip"')
    sps_ip = cursor.fetchone()
    conn.close()

    sps_ip = sps_ip[0] if sps_ip else "192.168.0.1"  # Fallback auf Standardwert

    return render_template('settings.html', sps_ip=sps_ip)

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

#Glas Entnommen
@app.route("/glas_entnommen", methods=["POST"])
def glas_entnommen():
    try:
        sps = SPSKommunikation(get_sps_ip())  # Hole die SPS-IP aus der Datenbank
        db_number = 130
        start_address = 0  # Startadresse für den String
        string_data = struct.pack(">BB20s", 20, 0, b"")  # STRING[20] auf '' setzen
        
        sps.write_db(db_number, start_address, string_data)
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

    try:
        print("Initialisiere Verbindung zur SPS...")
        sps = SPSKommunikation(get_sps_ip())  # Prüfen, ob IP korrekt geladen wird
        print(f"Verbindung zur SPS erfolgreich: {sps.ip}")
    except Exception as e:
        print(f"Fehler beim Verbinden zur SPS: {e}")
        flash("Verbindung zur SPS fehlgeschlagen.", "danger")
        return render_template('flaschen_alle.html', flaschen=[])

    # POST: Speichern der Änderungen
    if request.method == 'POST':
        try:
            for i in range(1, array_length + 1):
                print(f"Verarbeite Änderungen für Flasche {i}...")
                flasche = UDTFlasche(
                    name=request.form[f'name_{i}'],
                    x=float(request.form[f'x_{i}']),
                    y=float(request.form[f'y_{i}']),
                    dosier_art=bool(request.form.get(f'dosier_art_{i}', 'off') == 'on'),
                    dosiermenge=int(request.form[f'dosiermenge_{i}']),
                    alkoholgehalt=float(request.form[f'alkoholgehalt_{i}'])
                )
                sps.write_flasche(db_number=db_number, index=i, flasche=flasche, udt_size=udt_size)
            flash("Änderungen erfolgreich gespeichert.", "success")
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")
            flash(f"Fehler beim Speichern der Flaschen: {e}", "danger")
        finally:
            sps.disconnect()
            return redirect(url_for('flaschen_alle'))

    # GET: Flaschen laden
    try:
        print("Lese Flaschen aus der SPS...")
        flaschen = read_udt_array(sps, db_number, array_start, udt_size, array_length)
        print(f"Flaschen geladen: {len(flaschen)}")
    except Exception as e:
        print(f"Fehler beim Laden der Flaschen: {e}")
        flash(f"Fehler beim Laden der Flaschen: {e}", "danger")
        flaschen = []
    finally:
        sps.disconnect()

    return render_template('flaschen_alle.html', flaschen=flaschen)


#Flasche Updaten
@app.route('/update_flasche/<int:index>', methods=['POST'])
def update_flasche(index):
    db_number = 120
    array_start = 0
    udt_size = 38

    # Formular-Daten auslesen
    flasche = UDTFlasche(
        name=request.form['name'],
        x=float(request.form['x']),
        y=float(request.form['y']),
        dosier_art=bool(int(request.form['dosier_art'])),
        dosiermenge=int(request.form['dosiermenge']),
        alkoholgehalt=float(request.form['alkoholgehalt'])
    )

    # Flasche in die SPS schreiben
    try:
        sps = SPSKommunikation("192.168.0.1")
        sps.write_flasche(db_number=db_number, index=index, flasche=flasche, udt_size=udt_size)
        sps.disconnect()
    except Exception as e:
        flash(f"Fehler beim Speichern der Flasche: {e}", "danger")
        return redirect(url_for('flaschen', index=index))

    flash(f"Flasche {index} erfolgreich gespeichert.", "success")
    return redirect(url_for('settings'))

#Cocktailbestellen
@app.route('/order_cocktail/<int:id>', methods=['POST'])
def order_cocktail(id):
    try:
        # Verbindung zur SPS herstellen
        sps = SPSKommunikation(get_sps_ip())
        
        # Cocktail-Daten aus der Datenbank abrufen
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

            # STRING-Daten mit Längenangabe für die SPS vorbereiten
            max_length = 20  # Maximale Länge des Strings
            actual_length = len(cocktail_name)
            if actual_length > max_length:
                cocktail_name = cocktail_name[:max_length]  # Kürzen auf maximale Länge
            string_data = bytes([max_length, actual_length]) + cocktail_name.ljust(max_length).encode('ascii')

            # Bestellung in die Tabelle `orders` eintragen
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')
            cursor.execute(
                '''
                INSERT INTO orders (cocktail_id, ip_address, user_agent)
                VALUES (?, ?, ?)
                ''',
                (id, ip_address, user_agent)
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

        # Zutaten und Mengen in die korrekten Indizes schreiben
        for ingredient in ingredients:
            flasche_name = ingredient['flasche_name']
            menge = int(ingredient['menge_ml'])
            
            # Index der Flasche herausfinden
            flaschen_index = next((i for i, flasche in enumerate(read_udt_array(sps, 120, 0, 38, 30)) if flasche.name == flasche_name), None)
            
            if flaschen_index is not None and flaschen_index < len(menge_array):
                menge_array[flaschen_index] = menge

        # Daten in die SPS schreiben
        db_number = 130
        sps.write_db(db_number, 3038, string_data)  # Name des Cocktails
        for i, menge in enumerate(menge_array):
            sps.write_db(db_number, 3060 + (i * 2), struct.pack('>H', menge))  # Mengen (als UInt)

        sps.disconnect()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Fehler bei der Bestellung: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    

# Route für die Hauptseite (Cocktailauswahl), sortiert nach dem höchsten Zählerwert
@app.route('/')
def index():
    conn = get_db_connection()
    # Cocktails absteigend nach `counter` sortieren, sodass der höchste Wert zuerst angezeigt wird
    cocktails = conn.execute('SELECT * FROM cocktails ORDER BY counter DESC').fetchall()
    conn.close()
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
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Cocktail löschen
            cursor.execute('DELETE FROM cocktails WHERE id = ?', (id,))
            logging.info(f"Cocktail {id} gelöscht aus 'cocktails'.")

            # Zugehörige Zutaten löschen
            cursor.execute('DELETE FROM cocktail_ingredients WHERE cocktail_id = ?', (id,))
            logging.info(f"Zutaten für Cocktail {id} gelöscht aus 'cocktail_ingredients'.")

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
    app.run(debug=True)