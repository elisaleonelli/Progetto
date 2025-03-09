from flask import Flask,request,redirect,url_for,render_template,session,flash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from secret import secret_key
from google.cloud import firestore, storage
from google.cloud import pubsub_v1
from google.auth import jwt
from joblib import load, dump
import json
import csv

# Classe utente per Flask-Login
class User(UserMixin):
    def __init__(self, email):
        self.id = email

# Creazione app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key  

# Configurazione Flask-Login
login = LoginManager(app)
login.login_view = 'paginainiziale'  # Pagina di login predefinita

# Simulazione database utenti
usersdb = {
    'elisaleonelli2000@gmail.com': 'Micetto',
    '266983@studenti.unimore.com': 'Universita'
}

# Flask-Login: funzione per caricare l'utente
@login.user_loader
def load_user(email): 
    return User(email) if email in usersdb else None

# Pagina iniziale
@app.route('/')
def paginainiziale():
    return redirect('/static/paginainiziale.html')  

# Pagina di login
@app.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/home') 

    email = request.form.get('email')
    password = request.form.get('password')

    if email in usersdb and password == usersdb[email]:
        login_user(User(email))
        return redirect('/home')  

    return redirect('/static/login.html')  

# Pagina home (protetta)
@app.route('/home')
@login_required
def home():
    return redirect('/static/home.html') 

# Logout
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect('/')

# Inizializza un contatore globale
order_count = 0
statistics_batch_size = 5  # Calcola le statistiche ogni X ordini ricevuti

@app.route('/raw_data', methods=['GET'])
def raw_data():
    # Crea una connessione al database Firestore
    db = firestore.Client.from_service_account_json('credentials.json', database='progettoleonelli')
    collection_ref = db.collection('Table1').document('Ordini')  # Aggiungi la tua collection

    # Controlla se il documento esiste
    if collection_ref.get().exists:
        # Ottieni i dati del documento
        data = collection_ref.get().to_dict()
        result = []

        # Estrai tutte le informazioni dal documento
        for order_id, order_data in data.items():
            # Estrai i singoli campi
            Delivery_ID = order_data.get('Delivery_ID')
            Delivery_age = order_data.get('Delivery_age')
            Delivery_ratings = order_data.get('Delivery_ratings')
            Restaurant_location = order_data.get('Restaurant_location', [])
            Delivery_location = order_data.get('Delivery_location', [])
            Type_of_order = order_data.get('Type_of_order')
            Type_of_vehicle = order_data.get('Type_of_vehicle')
            Time_taken = order_data.get('Time_taken')

            # Crea una lista di ordini con i dati necessari
            result.append({
                'ID': order_id,  # ID dell'ordine (chiave del documento)
                'Delivery_ID': Delivery_ID,
                'Delivery_age': Delivery_age,
                'Delivery_ratings': Delivery_ratings,
                'Restaurant_location': Restaurant_location,  # [latitude, longitude]
                'Delivery_location': Delivery_location,  # [latitude, longitude]
                'Type_of_order': Type_of_order,
                'Type_of_vehicle': Type_of_vehicle,
                'Time_taken': Time_taken
            })

        # Restituisci i dati in formato JSON
        return json.dumps(result, indent=4)
    else:
        return json.dumps({'error': 'document not found'}), 404
    
@app.route('/static/maps', methods=['GET'])
def maps():
    # Restituisci semplicemente la pagina HTML della mappa
    return render_template('maps.html')

@app.route('/salvataggio', methods=['POST', 'GET'])
def store():
    global order_count  # Usa il contatore globale

    # Estrai l'ID dell'ordine dalla request
    delivery = json.loads(request.values['Data'])  # Estrai i dati dell'ordine
    ID = delivery['ID']  # Estrai l'ID dell'ordine

    val = {
        'Delivery_ID': delivery['Delivery_ID'],
        'Delivery_age': delivery['Delivery_age'],
        'Delivery_ratings': delivery['Delivery_ratings'],
        'Restaurant_location': delivery['Restaurant_location'],
        'Delivery_location': delivery['Delivery_location'],
        'Type_of_order': delivery['Type_of_order'],
        'Type_of_vehicle': delivery['Type_of_vehicle'],
        'Time_taken': delivery['Time_taken']
    }  # Crea un nuovo dizionario con i dati dell'ordine

    db = firestore.Client.from_service_account_json('credentials.json', database='progettoleonelli')
    doc_ref = db.collection('Table1').document('Ordini')  # Riferimento al documento "Ordini"

    if doc_ref.get().exists:
        # Se il documento esiste, aggiorno il Firestore
        diz = doc_ref.get().to_dict()  # Ottieni la versione attuale dei dati
        diz[ID] = val  # Aggiungi il nuovo ordine al dizionario
        doc_ref.update({ID: val}) # Aggiorna il documento
    else:
        # Se il documento non esiste, lo creo e inserisco il primo ordine
        doc_ref.set({ID: val})

    order_count += 1  # Incrementa il contatore degli ordini ricevuti

    # Calcolare le statistiche ogni X ordini ricevuti
    if order_count % statistics_batch_size == 0:
        calculate_delivery_time_statistics()

    return f"Dati memorizzati con successo"

# Funzione per calcolare le statistiche del tempo di consegna, valutazione media e numero di consegne
def calculate_delivery_time_statistics():
    db = firestore.Client.from_service_account_json('credentials.json', database='progettoleonelli')
    doc_ref = db.collection('Table1').document('Ordini')

    if doc_ref.get().exists:
        diz = doc_ref.get().to_dict()
        driver_stats = {}

        # Controlliamo il contenuto del dizionario per debug
        if not diz:
            print("Errore: dizionario vuoto o struttura non corretta")
            return

        for ordine in diz.values():
            driver_id = ordine.get('Delivery_ID')  # Usa .get() per evitare errori di chiave

            if driver_id is None:
                print(f"Errore: 'Delivery_ID' mancante in ordine: {ordine}")
                continue  # Salta l'ordine se manca l'ID del driver

            delivery_time = float(ordine.get('Time_taken', 0))  # Converte in float e imposta 0 se mancante
            delivery_rating = float(ordine.get('Delivery_ratings', 0))  # Converte in float e imposta 0 se mancante

            if driver_id not in driver_stats:
                driver_stats[driver_id] = {
                    'total_time': 0, 
                    'order_count': 0, 
                    'total_rating': 0
                }

            driver_stats[driver_id]['total_time'] += delivery_time
            driver_stats[driver_id]['order_count'] += 1
            driver_stats[driver_id]['total_rating'] += delivery_rating

        driver_avg_time = {}
        driver_avg_rating = {}
        driver_total_orders = {}

        for driver_id, stats in driver_stats.items():
            avg_time = stats['total_time'] / stats['order_count']
            avg_rating = stats['total_rating'] / stats['order_count']
            total_orders = stats['order_count']

            driver_avg_time[driver_id] = avg_time
            driver_avg_rating[driver_id] = avg_rating
            driver_total_orders[driver_id] = total_orders

        # Salvataggio delle statistiche nel Firestore
        save_statistics_to_firestore(driver_avg_time, driver_avg_rating, driver_total_orders)

# Funzione per salvare le statistiche nel database
def save_statistics_to_firestore(avg_time, avg_rating, total_orders):
    db = firestore.Client.from_service_account_json('credentials.json', database='progettoleonelli')
    stats_ref = db.collection('Driver_Statistics').document('Statistics')
    stats_ref.set({
    'average_times': avg_time,  # Salviamo il dizionario
    'average_ratings': avg_rating,
    'total_orders': total_orders
    })
    #print("Salvataggio statistiche:", avg_time, avg_rating, total_orders)

@app.route('/static/statistics', methods=['GET'])
def statistics_data():
        db = firestore.Client.from_service_account_json('credentials.json', database='progettoleonelli')
        doc_ref = db.collection('Driver_Statistics').document('Statistics')

        # Recupera i dati da Firestore
        if doc_ref.get().exists:
            stats = doc_ref.get().to_dict()

            # Estrai i dati per le statistiche da visualizzare
            avg_times = stats.get('average_times', {})
            avg_ratings = stats.get('average_ratings', {})
            total_orders = stats.get('total_orders', {})

            # Prepara i dati per il grafico
            chart_data = []
            for driver_id in avg_times.keys():
                chart_data.append([driver_id, avg_times.get(driver_id, 0), avg_ratings.get(driver_id, 0), total_orders.get(driver_id, 0)])

            # Passa i dati al template
            return render_template('statistics.html', chart_data=chart_data)

        return render_template('statistics.html')  # In caso di errore, comunque rendi il template   




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
