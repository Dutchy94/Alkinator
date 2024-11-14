import sqlite3

# Verbindung zur Datenbank erstellen
conn = sqlite3.connect('cocktails.db')
cursor = conn.cursor()

# Tabelle für Cocktails erstellen, falls sie noch nicht existiert
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cocktails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ingredients TEXT NOT NULL,
        description TEXT,
        image_path TEXT
    )
''')

# Änderungen speichern und Verbindung schließen
conn.commit()
conn.close()

print("Datenbank und Tabelle 'cocktails' erfolgreich mit allen erforderlichen Feldern erstellt.")
