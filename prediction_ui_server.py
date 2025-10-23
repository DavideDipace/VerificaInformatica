import os
import joblib # Per caricare il modello .pkl
import pandas as pd
from flask import Flask, request, jsonify, render_template # Aggiunto render_template
from dotenv import load_dotenv
from flask_cors import CORS

# --- 1. CONFIGURAZIONE E CARICAMENTO MODELLO ---

load_dotenv() # Carica .env se necessario

# Inizializza l'app Flask
# Notare 'template_folder=' per dire a Flask dove trovare i file HTML
app = Flask(__name__, template_folder='templates') 
CORS(app) # Permetti richieste cross-origin se necessario

# Carica la pipeline del modello addestrato (preprocessore + classificatore)
model_filename = 'model.pkl'
try:
    model = joblib.load(model_filename)
    print(f"Modello '{model_filename}' caricato con successo.")
except FileNotFoundError:
    print(f"ERRORE: File del modello '{model_filename}' non trovato.")
    print("Assicurati di aver eseguito prima 'train_model.py'.")
    model = None 
except Exception as e:
    print(f"Errore durante il caricamento del modello: {e}")
    model = None

# Definisci i nomi delle feature attese (devono corrispondere all'addestramento)
EXPECTED_FEATURES = ['Potenza_kW', 'NIL', 'RicaricheMedieGiornaliere', 'DurataMediaMinuti', 'EnergiaMediaKWh']

# --- 2. ROTTA PER MOSTRARE LA PAGINA WEB (PUNTO 7) ---

@app.route('/', methods=['GET'])
def prediction_page():
    """
    Mostra la pagina HTML con il form per inserire i dati.
    """
    # Dice a Flask di cercare e restituire il file 'predict_page_combined.html'
    # dalla cartella 'templates'
    return render_template('predict_page_combined.html')

# --- 3. ENDPOINT API DI PREDIZIONE (PUNTO 6) ---

@app.route('/predict', methods=['POST'])
def predict_usage():
    """
    Endpoint API per predire l'utilizzo di una colonnina.
    Accetta un JSON con le features della colonnina dal form HTML.
    Restituisce la predizione ('basso', 'medio', 'alto').
    """
    # Controlla se il modello è stato caricato correttamente
    if model is None:
        return jsonify({"error": "Modello non caricato. Impossibile fare predizioni."}), 500

    # Ottieni i dati JSON inviati dal JavaScript della pagina HTML
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Nessun dato JSON ricevuto."}), 400

        # --- Validazione e Preparazione Dati ---
        # 1. Controlla feature mancanti
        missing_features = [feature for feature in EXPECTED_FEATURES if feature not in data]
        if missing_features:
            return jsonify({"error": f"Dati mancanti: {', '.join(missing_features)}"}), 400

        # 2. Converti in DataFrame pandas
        input_df = pd.DataFrame([data])
        input_df = input_df[EXPECTED_FEATURES] # Assicura ordine corretto colonne

        # 3. Conversione tipi (importante!)
        try:
            input_df['Potenza_kW'] = pd.to_numeric(input_df['Potenza_kW'])
            input_df['RicaricheMedieGiornaliere'] = pd.to_numeric(input_df['RicaricheMedieGiornaliere'])
            input_df['DurataMediaMinuti'] = pd.to_numeric(input_df['DurataMediaMinuti'])
            input_df['EnergiaMediaKWh'] = pd.to_numeric(input_df['EnergiaMediaKWh'])
            input_df['NIL'] = input_df['NIL'].astype(str)
        except ValueError as ve:
             return jsonify({"error": f"Errore nella conversione dei tipi di dati: {ve}"}), 400

        # --- Esegui la Predizione ---
        # Il modello (pipeline) applica automaticamente preprocessing e predizione
        prediction = model.predict(input_df) 

        # Estrai il risultato (solitamente il primo elemento di un array)
        predicted_class = prediction[0]

        # Restituisci la predizione come JSON alla pagina HTML
        return jsonify({"predicted_usage_level": predicted_class})

    except Exception as e:
        print(f"Errore durante la predizione: {e}") # Logga l'errore per debug
        return jsonify({"error": f"Errore interno del server: {str(e)}"}), 500

# --- 4. AVVIA IL SERVER ---
if __name__ == '__main__':
    # Esegui sulla porta 5001 (o un'altra porta libera)
    # Usa host 0.0.0.0 per l'accesso da Codespaces
    print("Avvio del server di predizione con UI sulla porta 5001...")
    print("Accedi a http://localhost:5001 (o all'URL pubblico di Codespaces)")
    app.run(debug=True, host='0.0.0.0', port=5001) # debug=True utile per lo sviluppo