import os
import joblib # To load the model
import pandas as pd
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

# --- 1. CONFIGURATION AND MODEL LOADING ---

load_dotenv() # Load .env variables if needed (though not strictly for prediction)

# Initialize Flask app
app = Flask(__name__)
CORS(app) # Allow requests from other origins (like your main app's frontend)

# Load the trained model pipeline (preprocessor + classifier)
model_filename = 'model.pkl'
try:
    model = joblib.load(model_filename)
    print(f"Modello '{model_filename}' caricato con successo.")
except FileNotFoundError:
    print(f"ERRORE: File del modello '{model_filename}' non trovato.")
    print("Assicurati di aver eseguito prima lo script 'train_model.py'.")
    model = None # Set model to None if loading failed
except Exception as e:
    print(f"Errore durante il caricamento del modello: {e}")
    model = None

# Define the expected feature names (must match training)
# These are the columns the model expects in the input DataFrame
EXPECTED_FEATURES = ['Potenza_kW', 'NIL', 'RicaricheMedieGiornaliere', 'DurataMediaMinuti', 'EnergiaMediaKWh']

# --- 2. PREDICTION ENDPOINT ---

@app.route('/predict', methods=['POST'])
def predict_usage():
    """
    Endpoint API per predire l'utilizzo di una colonnina.
    Accetta un JSON con le features della colonnina.
    Restituisce la predizione ('basso', 'medio', 'alto').
    """
    if model is None:
        return jsonify({"error": "Modello non caricato correttamente. Impossibile fare predizioni."}), 500

    # Get data from the POST request
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Nessun dato JSON ricevuto."}), 400

        # --- Data Validation and Preparation ---
        # 1. Check if all expected features are present in the input
        missing_features = [feature for feature in EXPECTED_FEATURES if feature not in data]
        if missing_features:
            return jsonify({"error": f"Dati mancanti: {', '.join(missing_features)}"}), 400

        # 2. Convert input JSON to a pandas DataFrame (model expects DataFrame)
        # Ensure the order of columns matches EXPECTED_FEATURES
        input_df = pd.DataFrame([data])
        input_df = input_df[EXPECTED_FEATURES] # Reorder columns just in case

        # 3. Basic type conversion (optional but good practice)
        try:
            input_df['Potenza_kW'] = pd.to_numeric(input_df['Potenza_kW'])
            input_df['RicaricheMedieGiornaliere'] = pd.to_numeric(input_df['RicaricheMedieGiornaliere'])
            input_df['DurataMediaMinuti'] = pd.to_numeric(input_df['DurataMediaMinuti'])
            input_df['EnergiaMediaKWh'] = pd.to_numeric(input_df['EnergiaMediaKWh'])
            input_df['NIL'] = input_df['NIL'].astype(str)
        except ValueError as ve:
             return jsonify({"error": f"Errore nella conversione dei tipi di dati: {ve}"}), 400

        # --- Make Prediction ---
        prediction = model.predict(input_df)

        # The prediction is usually an array, get the first element
        predicted_class = prediction[0]

        # Return the prediction as JSON
        return jsonify({"predicted_usage_level": predicted_class})

    except Exception as e:
        print(f"Errore durante la predizione: {e}") # Log the error server-side
        return jsonify({"error": f"Errore interno del server durante la predizione: {str(e)}"}), 500

# --- 3. RUN THE SERVER ---
if __name__ == '__main__':
    # Run on a DIFFERENT port than the main app (e.g., 5001)
    # Use 0.0.0.0 host for Codespaces access
    app.run(debug=False, host='0.0.0.0', port=5001) # debug=False recommended for prediction server