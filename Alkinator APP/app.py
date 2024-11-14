from flask import Flask, render_template, request, redirect, url_for, flash
import config

app = Flask(__name__)
app.secret_key = "geheime_schluessel"  # Für Flash-Meldungen und Session-Handling

# Route für die Hauptseite (Cocktailauswahl)
@app.route('/')
def index():
    # Hier könntest du eine Liste der verfügbaren Cocktails aus der Datenbank abrufen
    cocktails = ["Mojito", "Pina Colada", "Caipirinha"]
    return render_template('index.html', cocktails=cocktails)

# Route für die Einstellungsseite für Flaschenparameter
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Verarbeite die Formulardaten für Flaschenparameter
        # z. B. speichere die Daten in einer Datenbank oder in einer Datei
        flash("Einstellungen für Flaschen wurden aktualisiert.", "success")
        return redirect(url_for('settings'))
    return render_template('settings.html')

# Route für die Cocktail-Erstellungsseite
@app.route('/create_cocktail', methods=['GET', 'POST'])
def create_cocktail():
    if request.method == 'POST':
        # Verarbeite die Formulardaten für den neuen Cocktail
        flash("Cocktail erfolgreich erstellt!", "success")
        return redirect(url_for('index'))
    return render_template('create_cocktail.html')

# Route für die grundlegenden Einstellungen (SPS IP, Rack, Slot)
@app.route('/basic_settings', methods=['GET', 'POST'])
def basic_settings():
    if request.method == 'POST':
        config.SPS_IP = request.form.get('sps_ip')
        config.RACK = request.form.get('rack')
        config.SLOT = request.form.get('slot')
        flash("Grundlegende Einstellungen wurden gespeichert.", "success")
        return redirect(url_for('basic_settings'))
    return render_template('basic_settings.html', sps_ip=config.SPS_IP, rack=config.RACK, slot=config.SLOT)

if __name__ == "__main__":
    app.run(debug=True)
