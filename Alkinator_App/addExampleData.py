import sqlite3

# Verbindung zur Datenbank erstellen
conn = sqlite3.connect('cocktails.db')
cursor = conn.cursor()

# Beispiel-Cocktails
cocktails = [
    ("Mojito", "Weißer Rum, Minze, Limettensaft, Zucker, Sodawasser", "Erfrischender Cocktail mit Minze und Limette"),
    ("Pina Colada", "Weißer Rum, Kokoscreme, Ananassaft", "Süßer und cremiger tropischer Cocktail"),
    ("Caipirinha", "Cachaça, Limette, Zucker", "Klassischer brasilianischer Cocktail mit Limetten"),
    ("Margarita", "Tequila, Limettensaft, Orangenlikör, Salzrand", "Beliebter mexikanischer Cocktail mit salzigem Rand"),
    ("Long Island Iced Tea", "Wodka, Tequila, Rum, Gin, Triple Sec, Zitronensaft, Cola", "Starker Cocktail mit Cola-Geschmack"),
    ("Mai Tai", "Rum, Limettensaft, Orangenlikör, Mandelsirup", "Fruchtiger Rum-Cocktail aus der Tiki-Kultur"),
    ("Cosmopolitan", "Wodka, Cranberrysaft, Limettensaft, Triple Sec", "Frischer Cocktail mit Cranberry- und Limettengeschmack"),
    ("Whiskey Sour", "Whiskey, Zitronensaft, Zuckersirup, Eiweiß (optional)", "Säuerlicher Cocktail auf Whiskey-Basis"),
    ("Daiquiri", "Weißer Rum, Limettensaft, Zuckersirup", "Klassischer Cocktail mit Rum und Limette"),
    ("Negroni", "Gin, roter Wermut, Campari", "Bitterer Cocktail mit kräftigem Geschmack"),
]

# Cocktails in die Datenbank einfügen
cursor.executemany('INSERT INTO cocktails (name, ingredients, description) VALUES (?, ?, ?)', cocktails)

# Änderungen speichern und Verbindung schließen
conn.commit()
conn.close()

print("Beispieldaten erfolgreich in die Datenbank eingefügt.")
