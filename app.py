import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func
from datetime import datetime
from dotenv import load_dotenv
from datetime import timedelta

# --- 1. CONFIGURAZIONE INIZIALE ---

# Carica le variabili dal file .env
load_dotenv()

# Inizializza l'app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# === AGGIUNGI QUESTA RIGA ===
# Imposta la scadenza automatica della sessione (es. 8 ore)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# Inizializza estensioni
db = SQLAlchemy(app)
CORS(app) # Permette al frontend JS di chiamare il backend

# Configurazione Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Se un utente non loggato visita una pagina protetta, viene mandato qui
login_manager.login_message = "Devi effettuare il login per accedere."


# --- 2. MODELLI DATABASE (Traduzione del tuo E/R) ---
# Usiamo UserMixin per integrare ACCOUNT con Flask-Login

class ACCOUNT(UserMixin, db.Model):
    __tablename__ = 'account'
    ID_Account = db.Column(db.Integer, primary_key=True)
    Email = db.Column(db.String(255), unique=True, nullable=False)
    Password = db.Column(db.String(255), nullable=False)
    Tipo_Account = db.Column(db.Enum('utente', 'admin', name='tipo_account'), nullable=False)
    Data_Creazione = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Flask-Login richiede questo metodo
    def get_id(self):
        return (self.ID_Account)

    # Metodi per la password
    def set_password(self, password):
        self.Password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.Password, password)

class UTENTE(db.Model):
    __tablename__ = 'utente'
    ID_Utente = db.Column(db.Integer, db.ForeignKey('account.ID_Account'), primary_key=True)
    Nome = db.Column(db.String(100), nullable=False)
    Cognome = db.Column(db.String(100), nullable=False)
    Codice_Fiscale = db.Column(db.String(16), unique=True, nullable=False)
    Telefono = db.Column(db.String(20))
    
    # Relazione 1-a-1 con Account
    account = db.relationship('ACCOUNT', backref=db.backref('utente', uselist=False))
    
    # Relazione 1-a-N con Auto, Ricarica, Prenotazione
    auto = db.relationship('AUTO', backref='proprietario', lazy=True)
    ricariche = db.relationship('RICARICA', backref='utente', lazy=True)
    prenotazioni = db.relationship('PRENOTAZIONE', backref='utente', lazy=True)

class AMMINISTRATORE(db.Model):
    __tablename__ = 'amministratore'
    ID_Amministratore = db.Column(db.Integer, db.ForeignKey('account.ID_Account'), primary_key=True)
    Nome = db.Column(db.String(100), nullable=False)
    Cognome = db.Column(db.String(100), nullable=False)
    Ruolo = db.Column(db.String(50), default='admin')
    
    # Relazione 1-a-1 con Account
    account = db.relationship('ACCOUNT', backref=db.backref('amministratore', uselist=False))
    predizioni = db.relationship('PREDIZIONE', backref='amministratore', lazy=True)

class AUTO(db.Model):
    __tablename__ = 'auto'
    Targa = db.Column(db.String(10), primary_key=True)
    Marca = db.Column(db.String(50), nullable=False)
    Modello = db.Column(db.String(50), nullable=False)
    ID_Utente = db.Column(db.Integer, db.ForeignKey('utente.ID_Utente'), nullable=False)

class COLONNINA(db.Model):
    __tablename__ = 'colonnina'
    ID_Colonnina = db.Column(db.Integer, primary_key=True)
    Indirizzo = db.Column(db.String(255), nullable=False)
    Latitudine = db.Column(db.Numeric(9, 6), nullable=False)
    Longitudine = db.Column(db.Numeric(9, 6), nullable=False)
    Potenza_kW = db.Column(db.Numeric(6, 2), nullable=False)
    NIL = db.Column(db.String(100))
    Stato = db.Column(db.Enum('disponibile', 'occupata', 'manutenzione', 'prenotata', name='stato_colonnina'), nullable=False, default='disponibile')
    Utilizzo_Classificato = db.Column(db.Enum('basso', 'medio', 'alto', name='livello_utilizzo'))
    
    ricariche = db.relationship('RICARICA', backref='colonnina', lazy=True)
    prenotazioni = db.relationship('PRENOTAZIONE', backref='colonnina', lazy=True)

class RICARICA(db.Model):
    __tablename__ = 'ricarica'
    ID_Ricarica = db.Column(db.Integer, primary_key=True)
    Data_Ora_Inizio = db.Column(db.DateTime(timezone=True), nullable=False)
    Data_Ora_Fine = db.Column(db.DateTime(timezone=True))
    Energia_Erogata_kWh = db.Column(db.Numeric(8, 3))
    ID_Utente = db.Column(db.Integer, db.ForeignKey('utente.ID_Utente'))
    ID_Colonnina = db.Column(db.Integer, db.ForeignKey('colonnina.ID_Colonnina'), nullable=False)
    Targa_Auto = db.Column(db.String(10), db.ForeignKey('auto.Targa'))

class PRENOTAZIONE(db.Model):
    __tablename__ = 'prenotazione'
    ID_Prenotazione = db.Column(db.Integer, primary_key=True)
    Data_Ora_Inizio_Prenotazione = db.Column(db.DateTime(timezone=True), nullable=False)
    Data_Ora_Fine_Prenotazione = db.Column(db.DateTime(timezone=True), nullable=False)
    Stato = db.Column(db.Enum('attiva', 'completata', 'cancellata', 'scaduta', name='stato_prenotazione'), nullable=False, default='attiva')
    ID_Utente = db.Column(db.Integer, db.ForeignKey('utente.ID_Utente'), nullable=False)
    ID_Colonnina = db.Column(db.Integer, db.ForeignKey('colonnina.ID_Colonnina'), nullable=False)
    Targa_Auto = db.Column(db.String(10), db.ForeignKey('auto.Targa'), nullable=False)

class PREDIZIONE(db.Model):
    __tablename__ = 'predizione'
    ID_Predizione = db.Column(db.Integer, primary_key=True)
    Data_Predizione = db.Column(db.DateTime(timezone=True), server_default=func.now())
    Periodo_Riferimento = db.Column(db.String(50), nullable=False)
    Latitudine_Prevista = db.Column(db.Numeric(9, 6))
    Longitudine_Prevista = db.Column(db.Numeric(9, 6))
    NIL_Riferimento = db.Column(db.String(100))
    Domanda_Prevista = db.Column(db.String(255))
    ID_Amministratore = db.Column(db.Integer, db.ForeignKey('amministratore.ID_Amministratore'))

# (Le tabelle SESSIONE e LOG_AZIONI non le implementiamo in SQLAlchemy
#  perché Flask-Login gestisce le sessioni e i log sono più complessi)


# --- 3. GESTIONE AUTENTICAZIONE (Req 1) ---

# Funzione richiesta da Flask-Login per caricare un utente dalla sessione
@login_manager.user_loader
def load_user(user_id):
    return ACCOUNT.query.get(int(user_id))

# Decoratore custom per proteggere le rotte admin
from functools import wraps

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.Tipo_Account != 'admin':
            abort(403) # Proibito
        return f(*args, **kwargs)
    return decorated_function

# Rotta per la pagina di login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('mappa'))

    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        user = ACCOUNT.query.filter_by(Email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            if user.Tipo_Account == 'admin':
                return jsonify({"status": "success", "redirect": url_for('admin_dashboard')})
            else:
                return jsonify({"status": "success", "redirect": url_for('mappa')})
        else:
            return jsonify({"status": "error", "message": "Email o password non validi"}), 401
            
    return render_template('login.html')

# Rotta per il logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- 4. ROTTE UTENTE (Req 2) ---

@app.route('/')
@app.route('/mappa')
@login_required
def mappa():
    # L'utente deve essere loggato per vedere la mappa
    return render_template('index.html', user_email=current_user.Email)

# API per fornire i dati alla mappa
@app.route('/api/colonnine', methods=['GET'])
@login_required
def get_colonnine():
    colonnine_db = COLONNINA.query.all()
    
    # Formattiamo i dati per la mappa (JSON)
    colonnine_json = []
    for c in colonnine_db:
        colonnine_json.append({
            "id": c.ID_Colonnina,
            "indirizzo": c.Indirizzo,
            "lat": float(c.Latitudine),
            "lng": float(c.Longitudine),
            "potenza_kw": float(c.Potenza_kW),
            "nil": c.NIL,
            "stato": c.Stato # Sarà 'disponibile' o 'occupata' ecc.
        })
    return jsonify(colonnine_json)

# API per prenotare una colonnina
@app.route('/api/prenota', methods=['POST'])
@login_required
def prenota_colonnina():
    if current_user.Tipo_Account != 'utente':
        return jsonify({"status": "error", "message": "Solo gli utenti possono prenotare"}), 403
        
    data = request.get_json()
    id_colonnina = data.get('id_colonnina')
    
    # Semplificazione: troviamo la prima auto dell'utente
    auto_utente = AUTO.query.filter_by(ID_Utente=current_user.ID_Account).first()
    if not auto_utente:
        return jsonify({"status": "error", "message": "Nessuna auto registrata per questo utente"}), 400

    colonnina = COLONNINA.query.get(id_colonnina)
    
    if not colonnina:
        return jsonify({"status": "error", "message": "Colonnina non trovata"}), 404
        
    if colonnina.Stato != 'disponibile':
        return jsonify({"status": "error", "message": "Colonnina non disponibile"}), 400
        
    # Logica di prenotazione (semplificata: prenotiamo per 1 ora da adesso)
    start_time = datetime.now()
    end_time = start_time + datetime.timedelta(hours=1)
    
    try:
        # Creiamo la prenotazione
        nuova_prenotazione = PRENOTAZIONE(
            Data_Ora_Inizio_Prenotazione=start_time,
            Data_Ora_Fine_Prenotazione=end_time,
            Stato='attiva',
            ID_Utente=current_user.ID_Account,
            ID_Colonnina=id_colonnina,
            Targa_Auto=auto_utente.Targa
        )
        
        # Aggiorniamo lo stato della colonnina
        colonnina.Stato = 'prenotata'
        
        db.session.add(nuova_prenotazione)
        db.session.commit()
        
        return jsonify({"status": "success", "message": f"Colonnina {id_colonnina} prenotata!"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Errore server: {str(e)}"}), 500


# --- 5. ROTTE AMMINISTRATORE (Req 3, 4, 5, 6) ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    # Pagina HTML del pannello admin
    return render_template('admin.html', user_email=current_user.Email)

# REQ 3: CRUD Colonnine
@app.route('/api/admin/colonnine', methods=['POST'])
@admin_required
def crea_colonnina():
    data = request.get_json()
    try:
        nuova_colonnina = COLONNINA(
            Indirizzo=data['indirizzo'],
            Latitudine=data['latitudine'],
            Longitudine=data['longitudine'],
            Potenza_kW=data['potenza_kw'],
            NIL=data['nil'],
            Stato=data.get('stato', 'disponibile')
        )
        db.session.add(nuova_colonnina)
        db.session.commit()
        return jsonify({"status": "success", "message": "Colonnina creata"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/admin/colonnine/<int:id>', methods=['PUT', 'DELETE'])
@admin_required
def gestisci_colonnina(id):
    colonnina = COLONNINA.query.get_or_404(id)
    
    if request.method == 'PUT':
        data = request.get_json()
        colonnina.Indirizzo = data.get('indirizzo', colonnina.Indirizzo)
        colonnina.Potenza_kW = data.get('potenza_kw', colonnina.Potenza_kW)
        colonnina.NIL = data.get('nil', colonnina.NIL)
        colonnina.Stato = data.get('stato', colonnina.Stato)
        db.session.commit()
        return jsonify({"status": "success", "message": "Colonnina aggiornata"})

    elif request.method == 'DELETE':
        db.session.delete(colonnina)
        db.session.commit()
        return jsonify({"status": "success", "message": "Colonnina eliminata"})

# REQ 4: CRUD Utenti (Semplificato: Creazione e Lista)
@app.route('/api/admin/utenti', methods=['GET', 'POST'])
@admin_required
def gestisci_utenti():
    if request.method == 'GET':
        utenti = UTENTE.query.join(ACCOUNT).all()
        utenti_json = [{
            "id": u.ID_Utente,
            "nome": u.Nome,
            "cognome": u.Cognome,
            "cf": u.Codice_Fiscale,
            "email": u.account.Email
        } for u in utenti]
        return jsonify(utenti_json)
        
    if request.method == 'POST':
        data = request.get_json()
        try:
            # 1. Crea l'account
            nuovo_account = ACCOUNT(
                Email=data['email'],
                Tipo_Account='utente'
            )
            nuovo_account.set_password(data['password'])
            db.session.add(nuovo_account)
            db.session.flush() # Ottiene l'ID prima del commit

            # 2. Crea l'utente
            nuovo_utente = UTENTE(
                ID_Utente=nuovo_account.ID_Account,
                Nome=data['nome'],
                Cognome=data['cognome'],
                Codice_Fiscale=data['cf']
            )
            db.session.add(nuovo_utente)
            db.session.commit()
            return jsonify({"status": "success", "message": "Utente creato"}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400

# REQ 5: Elenco ricariche totali
@app.route('/api/admin/ricariche', methods=['GET'])
@admin_required
def get_ricariche():
    # Join tra Ricarica, Utente e Colonnina per avere dati leggibili
    ricariche_db = db.session.query(
        RICARICA.ID_Ricarica,
        RICARICA.Data_Ora_Inizio,
        RICARICA.Data_Ora_Fine,
        RICARICA.Energia_Erogata_kWh,
        UTENTE.Nome,
        UTENTE.Cognome,
        COLONNINA.Indirizzo
    ).join(UTENTE, RICARICA.ID_Utente == UTENTE.ID_Utente)\
     .join(COLONNINA, RICARICA.ID_Colonnina == COLONNINA.ID_Colonnina)\
     .order_by(RICARICA.Data_Ora_Inizio.desc())\
     .all()
     
    ricariche_json = [{
        "id": r[0],
        "inizio": r[1].isoformat(),
        "fine": r[2].isoformat() if r[2] else None,
        "kwh": float(r[3]) if r[3] else None,
        "utente": f"{r[4]} {r[5]}",
        "colonnina": r[6]
    } for r in ricariche_db]
    
    return jsonify(ricariche_json)

# ... (tutto il codice precedente fino a @admin_required) ...

# REQ 6: Statistiche ricariche per quartiere (NIL)
@app.route('/api/admin/statistiche/ricariche_giorno', methods=['GET'])
@admin_required
def get_statistiche_nil():
    quartiere_nil = request.args.get('nil')
    if not quartiere_nil:
        return jsonify({"status": "error", "message": "Devi specificare un parametro 'nil' (quartiere)"}), 400

    try:
        # Eseguiamo una query complessa:
        # 1. Filtra le colonnine per NIL
        # 2. Si unisce alle ricariche
        # 3. Raggruppa le ricariche per giorno
        # 4. Conta le ricariche per quel giorno
        stats = db.session.query(
            func.date(RICARICA.Data_Ora_Inizio).label('giorno'),
            func.count(RICARICA.ID_Ricarica).label('totale_ricariche')
        ).join(COLONNINA, RICARICA.ID_Colonnina == COLONNINA.ID_Colonnina)\
         .filter(COLONNINA.NIL == quartiere_nil)\
         .group_by(func.date(RICARICA.Data_Ora_Inizio))\
         .order_by(func.date(RICARICA.Data_Ora_Inizio))\
         .all()
        
        # Formattiamo i dati per un grafico (es. Chart.js)
        labels = [r.giorno.strftime('%Y-%m-%d') for r in stats]
        data = [r.totale_ricariche for r in stats]
        
        return jsonify({"status": "success", "nil": quartiere_nil, "labels": labels, "data": data})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 6. COMANDO PER INIZIALIZZARE IL DB ---
# Assicurati di avere 'from datetime import datetime' all'inizio del file app.py

@app.cli.command("init-db")
def init_db_command():
    """Pulisce il DB, crea le tabelle e inserisce tutti i dati di test."""
    with app.app_context():
        
        print("Inizio inizializzazione... Disabilito i controlli FK.")
        # === AGGIUNGI QUESTA RIGA ===
        db.session.execute(db.text('SET FOREIGN_KEY_CHECKS=0;'))
        # ============================

        # 1. Pulisce tutto (elimina le tabelle vecchie)
        db.drop_all()
        print("Database pulito.")
        
        # 2. Crea le tabelle nuove
        db.create_all()
        print("Tabelle create.")

        # === AGGIUNGI QUESTA RIGA ===
        db.session.execute(db.text('SET FOREIGN_KEY_CHECKS=1;'))
        # ============================
        print("Controlli FK riabilitati.")

        # --- 3. CREA ADMIN ---
        try:
            admin_account = ACCOUNT(
                Email='admin@comune.milano.it',
                Tipo_Account='admin'
            )
            admin_account.set_password('admin123')
            db.session.add(admin_account)
            db.session.flush() 
            
            admin_profile = AMMINISTRATORE(
                ID_Amministratore=admin_account.ID_Account,
                Nome='Admin',
                Cognome='Comune',
                Ruolo='Super Admin'
            )
            db.session.add(admin_profile)
            print("Admin di default (admin@comune.milano.it / admin123) creato.")

            # --- 4. CREA UTENTI DI ESEMPIO (Mario, Giulia, Luca) ---
            
            # MARIO ROSSI (password: utente123)
            user1_acc = ACCOUNT(Email='mario.rossi@email.it', Tipo_Account='utente')
            user1_acc.set_password('utente123') # Password
            db.session.add(user1_acc)
            db.session.flush()
            
            user1_profile = UTENTE(ID_Utente=user1_acc.ID_Account, Nome='Mario', Cognome='Rossi', Codice_Fiscale='RSSMRA80A01H501A', Telefono='3331234567')
            db.session.add(user1_profile)
            
            auto1_1 = AUTO(Targa='GA123ZZ', Marca='Tesla', Modello='Model 3', ID_Utente=user1_acc.ID_Account)
            auto1_2 = AUTO(Targa='GA456AA', Marca='Volkswagen', Modello='ID.3', ID_Utente=user1_acc.ID_Account)
            db.session.add_all([auto1_1, auto1_2])
            print("Utente 'mario.rossi' (pass: utente123) creato.")

            # GIULIA BIANCHI (password: utente123)
            user2_acc = ACCOUNT(Email='giulia.bianchi@email.it', Tipo_Account='utente')
            user2_acc.set_password('utente123')
            db.session.add(user2_acc)
            db.session.flush()
            
            user2_profile = UTENTE(ID_Utente=user2_acc.ID_Account, Nome='Giulia', Cognome='Bianchi', Codice_Fiscale='BNCGLI85A41H501B', Telefono='3387654321')
            db.session.add(user2_profile)
            
            auto2_1 = AUTO(Targa='FY987WX', Marca='Fiat', Modello='500e', ID_Utente=user2_acc.ID_Account)
            db.session.add(auto2_1)
            print("Utente 'giulia.bianchi' (pass: utente123) creato.")
            
            # LUCA VERDI (password: utente123)
            user3_acc = ACCOUNT(Email='luca.verdi@email.it', Tipo_Account='utente')
            user3_acc.set_password('utente123')
            db.session.add(user3_acc)
            db.session.flush()
            
            user3_profile = UTENTE(ID_Utente=user3_acc.ID_Account, Nome='Luca', Cognome='Verdi', Codice_Fiscale='VRDLRU90A01H501C', Telefono='3471122334')
            db.session.add(user3_profile)
            
            auto3_1 = AUTO(Targa='EX456VB', Marca='Renault', Modello='Zoe', ID_Utente=user3_acc.ID_Account)
            db.session.add(auto3_1)
            print("Utente 'luca.verdi' (pass: utente123) creato.")

            # --- 5. CREA COLONNINE DI ESEMPIO ---
            c1 = COLONNINA(Indirizzo='Piazza del Duomo, 20121 Milano MI', Latitudine=45.4642, Longitudine=9.1900, Potenza_kW=50.0, NIL='Duomo')
            c2 = COLONNINA(Indirizzo='Via Montenapoleone, 20121 Milano MI', Latitudine=45.4687, Longitudine=9.1950, Potenza_kW=22.0, NIL='Duomo')
            c3 = COLONNINA(Indirizzo='Corso Buenos Aires, 42, 20124 Milano MI', Latitudine=45.4777, Longitudine=9.2132, Potenza_kW=50.0, NIL='Buenos Aires - Venezia')
            c4 = COLONNINA(Indirizzo='Piazzale Loreto, 20127 Milano MI', Latitudine=45.4855, Longitudine=9.2185, Potenza_kW=22.0, NIL='Loreto')
            c5 = COLONNINA(Indirizzo='Viale Papiniano, 59, 20123 Milano MI', Latitudine=45.4590, Longitudine=9.1685, Potenza_kW=50.0, NIL='Porta Genova')
            c6 = COLONNINA(Indirizzo='Via Alserio, 20159 Milano MI', Latitudine=45.4883, Longitudine=9.1771, Potenza_kW=22.0, NIL='Isola')
            c7 = COLONNINA(Indirizzo='Piazza Gae Aulenti, 20124 Milano MI', Latitudine=45.4837, Longitudine=9.1904, Potenza_kW=75.0, NIL='Porta Garibaldi')
            db.session.add_all([c1, c2, c3, c4, c5, c6, c7])
            print("Colonnine di esempio create.")
            
            # Commit per salvare utenti e colonnine e ottenere i loro ID
            db.session.commit()
            
            # --- 6. CREA RICARICHE E PRENOTAZIONI DI ESEMPIO ---
            r1 = RICARICA(Data_Ora_Inizio=datetime(2025, 10, 20, 8, 30, 0), Data_Ora_Fine=datetime(2025, 10, 20, 9, 15, 0), Energia_Erogata_kWh=35.500, ID_Utente=2, ID_Colonnina=1, Targa_Auto='GA123ZZ')
            r2 = RICARICA(Data_Ora_Inizio=datetime(2025, 10, 21, 14, 0, 0), Data_Ora_Fine=datetime(2025, 10, 21, 15, 30, 0), Energia_Erogata_kWh=48.200, ID_Utente=3, ID_Colonnina=5, Targa_Auto='FY987WX')
            r3 = RICARICA(Data_Ora_Inizio=datetime(2025, 10, 23, 9, 0, 0), ID_Utente=4, ID_Colonnina=3, Targa_Auto='EX456VB') # In corso
            r4 = RICARICA(Data_Ora_Inizio=datetime(2025, 10, 22, 18, 0, 0), Data_Ora_Fine=datetime(2025, 10, 22, 18, 45, 0), Energia_Erogata_kWh=20.000, ID_Utente=2, ID_Colonnina=2, Targa_Auto='GA456AA')
            r5 = RICARICA(Data_Ora_Inizio=datetime(2025, 10, 23, 8, 45, 0), ID_Utente=2, ID_Colonnina=7, Targa_Auto='GA123ZZ') # In corso
            p1 = PRENOTAZIONE(Data_Ora_Inizio_Prenotazione=datetime(2025, 10, 23, 10, 0, 0), Data_Ora_Fine_Prenotazione=datetime(2025, 10, 23, 11, 0, 0), Stato='attiva', ID_Utente=3, ID_Colonnina=6, Targa_Auto='FY987WX')
            db.session.add_all([r1, r2, r3, r4, r5, p1])

            # --- 7. AGGIORNA STATO COLONNINE ---
            col_occ_1 = COLONNINA.query.get(3)
            col_occ_2 = COLONNINA.query.get(7)
            col_man = COLONNINA.query.get(4)
            col_pren = COLONNINA.query.get(6)
            
            if col_occ_1: col_occ_1.Stato = 'occupata'
            if col_occ_2: col_occ_2.Stato = 'occupata'
            if col_man: col_man.Stato = 'manutenzione'
            if col_pren: col_pren.Stato = 'prenotata'
            
            # Commit finale
            db.session.commit()
            print("Database inizializzato e popolato con dati di test.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore durante l'inizializzazione del DB: {e}")

# === NUOVO COMANDO PER RESETTARE LA PASSWORD DI LUCA ===
@app.cli.command("reset-luca-password")
def reset_luca_password_command():
    """Trova l'utente luca.verdi@email.it e reimposta la sua password a 'utente123'."""
    with app.app_context():
        user_account = ACCOUNT.query.filter_by(Email='luca.verdi@email.it').first()
        if user_account:
            user_account.set_password('utente123')
            db.session.commit()
            print("Password per 'luca.verdi@email.it' reimpostata a 'utente123'.")
        else:
            print("ERRORE: Utente 'luca.verdi@email.it' non trovato nel database.")
# =======================================================

# --- 7. AVVIO APPLICAZIONE ---
if __name__ == '__main__':
    # '0.0.0.0' è necessario per esporre il server in un Codespace
    app.run(debug=True, host='0.0.0.0', port=5000)