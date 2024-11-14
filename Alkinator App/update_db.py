import sqlite3

# Verbindung zur Datenbank erstellen
conn = sqlite3.connect('cocktails.db')
cursor = conn.cursor()

# Neues Feld für den Bildpfad hinzufügen, falls es noch nicht existiert
cursor.execute('''
    ALTER TABLE cocktails
    ADD COLUMN image_path TEXT
''')

conn.commit()
conn.close()

print("Feld 'image_path' erfolgreich zur Tabelle 'cocktails' hinzugefügt.")
