import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = "geheime_schluessel"
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Ordner für Bild-Uploads
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # Max. Dateigröße 2 MB

# Funktion zur Verbindung mit der Datenbank
def get_db_connection():
    conn = sqlite3.connect('cocktails.db')
    conn.row_factory = sqlite3.Row
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


@app.route('/order_logs')
def order_logs():
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders').fetchall()
    conn.close()
    return render_template('order_logs.html', orders=orders)



#Einstellungen
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Speichern der Einstellungen
        settings_data = {
            'setting1': request.form['setting1'],
            'setting2': request.form['setting2']
        }
        save_settings('settings', settings_data)
        flash("Einstellungen erfolgreich gespeichert!", "success")
        return redirect(url_for('settings'))

    # Laden der vorhandenen Einstellungen für das Template
    settings = get_settings('settings')
    print("Geladene Einstellungen:", settings)  # Debugging-Ausgabe
    return render_template('settings.html', settings=settings)

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

#Cocktailbestellen
@app.route('/order_cocktail/<int:id>', methods=['POST'])
def order_cocktail(id):
    try:
        # Versucht, die Bestellung zu loggen
        log_order(id)
        return jsonify({"success": True})
    except Exception as e:
        # Debugging-Informationen bei Fehlern
        print(f"Fehler beim Verarbeiten der Bestellung für Cocktail ID {id}: {e}")
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
    conn = get_db_connection()
    cocktail = conn.execute('SELECT * FROM cocktails WHERE id = ?', (id,)).fetchone()

    if cocktail is None:
        flash("Cocktail mit dieser ID existiert nicht.", "danger")
        conn.close()
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Daten aus dem Formular lesen
        name = request.form['name']
        ingredients = request.form['ingredients']
        description = request.form['description']
        image_file = request.files['image']
        
        # Bildpfad aktualisieren, falls neues Bild hochgeladen wird
        image_path = cocktail['image_path']
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        # Cocktail-Daten in der Datenbank aktualisieren
        conn.execute('''
            UPDATE cocktails SET name = ?, ingredients = ?, description = ?, image_path = ?
            WHERE id = ?
        ''', (name, ingredients, description, image_path, id))
        conn.commit()
        conn.close()

        flash("Cocktail erfolgreich aktualisiert!", "success")
        
        # Nach dem Speichern zur Hauptseite umleiten
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit_cocktail.html', cocktail=cocktail)

@app.route('/remove_image_path/<int:id>', methods=['POST'])
def remove_image_path(id):
    conn = get_db_connection()
    cocktail = conn.execute('SELECT * FROM cocktails WHERE id = ?', (id,)).fetchone()

    if cocktail is None:
        return jsonify({"error": "Cocktail mit dieser ID existiert nicht."}), 404

    # Bildpfad in der Datenbank auf NULL setzen
    conn.execute('UPDATE cocktails SET image_path = NULL WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})  # JSON-Antwort zurückgeben


# Route zum Erstellen eines neuen Cocktails
@app.route('/create_cocktail', methods=['GET', 'POST'])
def create_cocktail():
    if request.method == 'POST':
        name = request.form['name']
        ingredients = request.form['ingredients']
        description = request.form['description']
        image_file = request.files['image']  # Bilddatei vom Formular

        # Überprüfen, ob die erforderlichen Felder ausgefüllt sind
        if not name or not ingredients:
            flash("Name und Zutaten sind erforderlich!", "danger")
            return redirect(url_for('create_cocktail'))

        # Bild speichern, falls hochgeladen
        image_path = None
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Sicherstellen, dass der Upload-Ordner existiert
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
                
            # Datei speichern
            image_file.save(image_path)

        # Cocktail-Daten in die Datenbank einfügen
        conn = get_db_connection()
        conn.execute('INSERT INTO cocktails (name, ingredients, description, image_path) VALUES (?, ?, ?, ?)',
                     (name, ingredients, description, image_path))
        conn.commit()
        conn.close()

        flash("Cocktail erfolgreich hinzugefügt!", "success")
        return redirect(url_for('index'))

    return render_template('create_cocktail.html')

# Überprüfen, ob Flash-Nachrichten funktionieren
print("Starte Flask-Anwendung...")

if __name__ == "__main__":
    app.run(debug=True)
