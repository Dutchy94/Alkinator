import sqlite3
from datetime import datetime, timedelta
import random

# Verbindung zur SQLite-Datenbank
db_path = "cocktails.db"  # Pfad zu deiner SQLite-Datenbank
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Beispielbenutzer
users = [
    {"username": "Hölker"},
    {"username": "Schülting"},
    {"username": "TestUser1"},
    {"username": "TestUser2"}
]

# Beispielcocktails
cocktails = [
    {"name": "Mojito", "description": "Ein erfrischender Cocktail mit Minze", "counter": 0},
    {"name": "Caipirinha", "description": "Brasilianischer Cocktail mit Limetten", "counter": 0},
    {"name": "Pina Colada", "description": "Fruchtiger Cocktail mit Ananas und Kokos", "counter": 0},
    {"name": "Tequila Sunrise", "description": "Fruchtiger Cocktail mit Orangensaft", "counter": 0}
]

# Alkoholgehalt für Flaschen
flaschen = [
    {"name": "Rum", "alkoholgehalt": 40},
    {"name": "Wodka", "alkoholgehalt": 37.5},
    {"name": "Tequila", "alkoholgehalt": 38},
    {"name": "Weißer Rum", "alkoholgehalt": 40}
]

# Testdaten einfügen
def insert_test_data():
    # Benutzer hinzufügen
    for user in users:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (user["username"],))
        if cursor.fetchone()[0] == 0:  # Benutzer existiert nicht
            cursor.execute("INSERT INTO users (username) VALUES (?)", (user["username"],))

    # Cocktails hinzufügen
    for cocktail in cocktails:
        cursor.execute(
            "INSERT INTO cocktails (name, description, counter, ingredients) VALUES (?, ?, ?, ?)",
            (
                cocktail["name"],
                cocktail["description"],
                cocktail["counter"],
                "Zutat1, Zutat2, Zutat3"  # Beispiel-Zutaten als CSV
            )
        )
        cocktail_id = cursor.lastrowid

        # Zutaten zufällig generieren (ohne Duplikate)
        used_flaschen = set()  # Verwendete Flaschen speichern
        for _ in range(3):  # 3 zufällige Flaschen
            while True:
                flasche = random.choice(flaschen)
                if flasche["name"] not in used_flaschen:
                    used_flaschen.add(flasche["name"])
                    break

            menge_ml = random.randint(10, 50)  # Menge zwischen 10 ml und 50 ml
            cursor.execute(
                "INSERT INTO cocktail_ingredients (cocktail_id, flasche_name, menge_ml) VALUES (?, ?, ?)",
                (cocktail_id, flasche["name"], menge_ml)
            )

    # Bestellungen hinzufügen
    for user in users:
        user_id = cursor.execute("SELECT id FROM users WHERE username = ?", (user["username"],)).fetchone()[0]
        for _ in range(5):  # 5 zufällige Bestellungen pro Benutzer
            cocktail = random.choice(cocktails)
            cocktail_id = cursor.execute("SELECT id FROM cocktails WHERE name = ?", (cocktail["name"],)).fetchone()[0]
            order_time = datetime.now() - timedelta(days=random.randint(0, 30))  # Zufällige Bestellzeit in den letzten 30 Tagen
            alcohol_content = random.uniform(0.1, 5.0)  # Zufälliger Alkoholgehalt in %
            cursor.execute(
                "INSERT INTO user_orders (user_id, cocktail_id, order_time, alcohol_content) VALUES (?, ?, ?, ?)",
                (user_id, cocktail_id, order_time, alcohol_content)
            )

    connection.commit()
    print("Testdaten erfolgreich eingefügt.")



# Testdaten einfügen
insert_test_data()

# Verbindung schließen
connection.close()
