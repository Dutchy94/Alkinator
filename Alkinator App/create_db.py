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



# Cocktail Inhalte mit UNIQUE-Einschränkung
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cocktail_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cocktail_id INTEGER NOT NULL,
        flasche_name TEXT NOT NULL,
        menge_ml REAL NOT NULL,
        UNIQUE(cocktail_id, flasche_name),  -- Eindeutige Einschränkung
        FOREIGN KEY(cocktail_id) REFERENCES cocktails(id)
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
cursor.execute('''
CREATE TABLE IF NOT EXISTS flaschen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    alkoholgehalt REAL NOT NULL
);
''')

# Standard-IP-Adresse der SPS hinzufügen, falls noch nicht vorhanden
cursor.execute('''
    INSERT OR IGNORE INTO settings (name, value) VALUES (?, ?)
''', ('sps_ip', '192.168.178.50'))

# Zusätzliche SPS-bezogene Einstellungen hinzufügen, falls benötigt
cursor.execute('''
    INSERT OR IGNORE INTO settings (name, value) VALUES (?, ?)
''', ('sps_rack', '0'))  # Beispiel für Rack-Nummer
cursor.execute('''
    INSERT OR IGNORE INTO settings (name, value) VALUES (?, ?)
''', ('sps_slot', '1'))  # Beispiel für Slot-Nummer
cursor.execute('''
    INSERT OR IGNORE INTO settings (name, value) VALUES ('global_cocktail_access', '0');
'''
)

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

cursor.execute('''
    ALTER TABLE orders ADD COLUMN user_id INTEGER;
''')

# Tabelle für Benutzer erstellen
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        user_agent TEXT,
        ip_address TEXT
    )
''')

cursor.execute('''CREATE TABLE IF NOT EXISTS user_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cocktail_id INTEGER NOT NULL,
    alcohol_content REAL NOT NULL,
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(cocktail_id) REFERENCES cocktails(id)
    );''')

cursor.execute('ALTER TABLE orders ADD COLUMN alcohol_content REAL DEFAULT 0.0;')

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

print("Datenbank und Tabellen erfolgreich mit allen erforderlichen Feldern erstellt.")
