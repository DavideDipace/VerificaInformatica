import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib # Usiamo joblib invece di pickle, è più efficiente per numpy arrays
from datetime import datetime, timedelta

# --- 1. Caricamento Configurazione e Connessione DB ---
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("Errore: DATABASE_URL non trovato nel file .env")
    exit()

try:
    engine = create_engine(DATABASE_URL)
    print("Connessione al database stabilita.")
except Exception as e:
    print(f"Errore di connessione al database: {e}")
    exit()

# --- 2. Estrazione Dati ---
try:
    # Query per estrarre dati colonnine e calcolare features dalle ricariche
    # Consideriamo le ricariche degli ultimi 90 giorni per definire l'utilizzo
    ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    
    query = f"""
    SELECT 
        c.ID_Colonnina,
        c.Potenza_kW,
        c.NIL,
        COUNT(r.ID_Ricarica) AS NumeroRicariche90gg,
        AVG(TIMESTAMPDIFF(MINUTE, r.Data_Ora_Inizio, r.Data_Ora_Fine)) AS DurataMediaMinuti,
        AVG(r.Energia_Erogata_kWh) AS EnergiaMediaKWh
    FROM 
        colonnina c
    LEFT JOIN 
        ricarica r ON c.ID_Colonnina = r.ID_Colonnina 
                  AND r.Data_Ora_Inizio >= '{ninety_days_ago}' 
                  AND r.Data_Ora_Fine IS NOT NULL -- Considera solo ricariche completate
    GROUP BY
        c.ID_Colonnina, c.Potenza_kW, c.NIL;
    """
    
    df = pd.read_sql(query, engine)
    print(f"Estratti dati per {len(df)} colonnine.")
    
    if df.empty:
        print("Nessun dato trovato per l'addestramento. Controlla le tabelle colonnina e ricarica.")
        exit()
        
except Exception as e:
    print(f"Errore durante l'estrazione dati: {e}")
    exit()

# --- 3. Feature Engineering e Creazione Target ---

# Calcola ricariche medie giornaliere
df['RicaricheMedieGiornaliere'] = df['NumeroRicariche90gg'] / 90.0

# Gestisci valori nulli (es. colonnine senza ricariche)
# Sintassi aggiornata per evitare FutureWarning
df['DurataMediaMinuti'] = df['DurataMediaMinuti'].fillna(0)
df['EnergiaMediaKWh'] = df['EnergiaMediaKWh'].fillna(0)
df['NIL'] = df['NIL'].fillna('Sconosciuto') # Gestiamo NIL mancanti

# Definiamo le regole per creare il target 'Utilizzo_Classificato'
# !!! SOGLIE MODIFICATE ARTIFICIALMENTE PER TEST CON POCHI DATI !!!
def classifica_utilizzo(ricariche_medie):
    if ricariche_medie == 0: # Nessuna ricarica negli ultimi 90gg
         return 'basso'
    elif ricariche_medie < 0.1: # Anche solo una ricarica fa scattare 'medio'
         return 'medio'
    else: # Più di 0.1 (circa 9 ricariche in 90gg)
         return 'alto' # Probabilmente non raggiungeremo 'alto' con i dati attuali

df['Utilizzo_Classificato'] = df['RicaricheMedieGiornaliere'].apply(classifica_utilizzo)

# Separiamo features (X) e target (y)
X = df[['Potenza_kW', 'NIL', 'RicaricheMedieGiornaliere', 'DurataMediaMinuti', 'EnergiaMediaKWh']]
y = df['Utilizzo_Classificato']

print("\nDistribuzione del target 'Utilizzo_Classificato':")
print(y.value_counts())

# Controllo se ci sono abbastanza classi per la classificazione
if len(y.unique()) < 2:
    print("\nErrore: Il target ha meno di 2 classi uniche. Impossibile addestrare un classificatore.")
    print("Possibili cause: poche ricariche nel DB o soglie di classificazione troppo estreme.")
    exit()

# --- 4. Preprocessing ---

# Identifica colonne numeriche e categoriche
numerical_features = ['Potenza_kW', 'RicaricheMedieGiornaliere', 'DurataMediaMinuti', 'EnergiaMediaKWh']
categorical_features = ['NIL']

# Crea i transformers
numeric_transformer = StandardScaler()
categorical_transformer = OneHotEncoder(handle_unknown='ignore') # Ignora NIL non visti in training

# Crea il preprocessor con ColumnTransformer
preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numerical_features),
        ('cat', categorical_transformer, categorical_features)
    ])

# --- 5. Definizione, Addestramento e Valutazione Modelli ---

# Definiamo i 3 modelli da confrontare
models = {
    "Logistic Regression": LogisticRegression(max_iter=1000, multi_class='auto', solver='liblinear'), # solver='liblinear' buono per piccoli dataset
    "Decision Tree": DecisionTreeClassifier(random_state=42),
    "Random Forest": RandomForestClassifier(random_state=42, n_estimators=100)
}

results = {}

# Dividiamo i dati in training e test set
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y) # stratify per mantenere proporzioni classi

print(f"\nDati divisi: {len(X_train)} training, {len(X_test)} test.")

best_model = None
best_accuracy = 0.0
best_model_name = ""

for name, model in models.items():
    print(f"\n--- Addestramento e Valutazione: {name} ---")
    
    # Crea la pipeline completa: preprocessing + modello
    pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                               ('classifier', model)])
    
    # Addestramento
    pipeline.fit(X_train, y_train)
    
    # Previsione sul test set
    y_pred = pipeline.predict(X_test)
    
    # Valutazione
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, zero_division=0)
    
    results[name] = {"accuracy": accuracy, "report": report}
    
    print(f"Accuracy: {accuracy:.4f}")
    print("Classification Report:")
    print(report)
    
    # Tieni traccia del modello migliore (basato sull'accuracy qui, ma potresti usare F1-score)
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        best_model = pipeline # Salviamo l'intera pipeline
        best_model_name = name

# --- 6. Selezione e Salvataggio del Modello Migliore ---

print(f"\nIl modello migliore è: {best_model_name} con Accuracy: {best_accuracy:.4f}")

# Salviamo la pipeline completa (preprocessor + modello addestrato)
model_filename = 'model.pkl' # Convenzione usare .pkl anche per joblib
try:
    joblib.dump(best_model, model_filename)
    print(f"Modello migliore salvato come '{model_filename}'")
except Exception as e:
    print(f"Errore durante il salvataggio del modello: {e}")