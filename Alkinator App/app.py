import os
from flask import Flask, render_template, request, redirect, url_for, flash
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

# Route für die Hauptseite (Cocktailauswahl)
@app.route('/')
def index():
    conn = get_db_connection()
    cocktails = conn.execute('SELECT * FROM cocktails').fetchall()
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
        name = request.form['name']
        ingredients = request.form['ingredients']
        description = request.form['description']
        image_file = request.files['image']  # Bilddatei vom Formular

        # Bild aktualisieren, falls neues Bild hochgeladen wird
        image_path = cocktail['image_path']
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        # Aktualisiere Cocktail-Daten in der Datenbank
        conn.execute('''
            UPDATE cocktails SET name = ?, ingredients = ?, description = ?, image_path = ?
            WHERE id = ?
        ''', (name, ingredients, description, image_path, id))
        conn.commit()
        conn.close()

        flash("Cocktail erfolgreich aktualisiert!", "success")
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit_cocktail.html', cocktail=cocktail)

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
