import sqlite3

# Verbindung zur Datenbank herstellen
conn = sqlite3.connect('cocktails.db')
cursor = conn.cursor()

# Tabelle `cocktails` erstellen, falls sie noch nicht existiert
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cocktails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ingredients TEXT NOT NULL,
        description TEXT,
        image_path TEXT,
        counter INTEGER DEFAULT 0
    )
''')

# Tabelle für allgemeine Einstellungen erstellen, falls sie noch nicht existiert
cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        value TEXT
    )
''')

# Tabelle für Grundeinstellungen erstellen, falls sie noch nicht existiert
cursor.execute('''
    CREATE TABLE IF NOT EXISTS basic_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        value TEXT
    )
''')

# Tabelle für Bestellungen erstellen, falls sie noch nicht existiert
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cocktail_id INTEGER,
        order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT,
        FOREIGN KEY(cocktail_id) REFERENCES cocktails(id)
    )
''')

# Überprüfen, ob das Feld `image_path` existiert; falls nicht, hinzufügen
try:
    cursor.execute('SELECT image_path FROM cocktails LIMIT 1')
except sqlite3.OperationalError:
    cursor.execute('ALTER TABLE cocktails ADD COLUMN image_path TEXT')
    print("Feld 'image_path' erfolgreich zur Tabelle 'cocktails' hinzugefügt.")

# Überprüfen, ob das Feld `counter` existiert; falls nicht, hinzufügen
try:
    cursor.execute('SELECT counter FROM cocktails LIMIT 1')
except sqlite3.OperationalError:
    cursor.execute('ALTER TABLE cocktails ADD COLUMN counter INTEGER DEFAULT 0')
    print("Feld 'counter' erfolgreich zur Tabelle 'cocktails' hinzugefügt.")

# Änderungen speichern und Verbindung schließen
conn.commit()
conn.close()

print("Datenbank und Tabelle 'cocktails' erfolgreich mit allen erforderlichen Feldern erstellt.")
