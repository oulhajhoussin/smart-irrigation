import paho.mqtt.client as mqtt
import json
import csv
import time
import os
import joblib
import numpy as np
from datetime import datetime  # ← NOUVEAU : Pour timestamps ISO
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None
try:
    import psutil
except ImportError:
    psutil = None
import requests

# Choix automatique du fichier en fonction de l'environnement (Test Windows vs Prod Raspberry)
CSV_FILE_LOCAL = "data_logger.csv"
CSV_FILE_RPI = "/home/pi/data_logger.csv"
CSV_FILE = CSV_FILE_LOCAL if os.path.exists(CSV_FILE_LOCAL) else CSV_FILE_RPI
if not os.path.exists(CSV_FILE) and os.path.exists("data_logger.csv"):
    CSV_FILE = "data_logger.csv"

TOPIC_CONTROL = "irrigation/control"

valve_states = {"node1": "OFF", "node2": "OFF"}
last_humidity = {"node1": None, "node2": None} # Mémoire FOG pour Inertie

# --- INJECTION Cerveau FOG (A.I.) ---
MODEL_PATH = 'fog_brain.pkl'
MLFLOW_SERVER = "http://192.168.100.97:5000"

def sync_mlflow_model():
    """Télécharge le dernier modèle validé depuis le registre MLflow"""
    print(f"🔄 [MLOps] Tentative de synchronisation avec MLflow ({MLFLOW_SERVER})...")
    try:
        # 1. On cherche l'ID de l'expérience par son nom
        exp_resp = requests.get(f"{MLFLOW_SERVER}/api/2.0/mlflow/experiments/get-by-name?experiment_name=Smart_Irrigation_Hybrid")
        if exp_resp.status_code != 200: 
            print("⚠️ [MLOps] Expérience non trouvée sur le serveur.")
            return None
        exp_id = exp_resp.json()['experiment']['experiment_id']
        
        # 2. On cherche le dernier run réussi
        search_payload = {"experiment_ids": [exp_id], "max_results": 1, "order_by": ["attributes.start_time DESC"]}
        response = requests.post(f"{MLFLOW_SERVER}/api/2.0/mlflow/runs/search", json=search_payload)
        
        if response.status_code == 200 and 'runs' in response.json():
            run_id = response.json()['runs'][0]['info']['run_id']
            # 3. Téléchargement de l'artefact (Chemin corrigé : models_fog/fog_brain.pkl)
            art_url = f"{MLFLOW_SERVER}/get-artifact?path=models_fog/fog_brain.pkl&run_id={run_id}"
            r = requests.get(art_url)
            if r.status_code == 200:
                with open(MODEL_PATH, 'wb') as f: f.write(r.content)
                print(f"✅ [MLOps] Nouveau cerveau téléchargé (Run: {run_id[:8]})")
                return joblib.load(MODEL_PATH)
            else:
                print(f"⚠️ [MLOps] Artefact non trouvé (Code {r.status_code})")
        else:
            print("⚠️ [MLOps] Aucun Run trouvé pour cette expérience.")
    except Exception as e:
        print(f"⚠️ [MLOps] Sync impossible : {e}")
    return None

try:
    # Tentative de sync au démarrage
    new_model = sync_mlflow_model()
    ai_fog = new_model if new_model else joblib.load(MODEL_PATH)
    print("🧠 [MLOps] Cerveau FOG charg\u00e9 avec succ\u00e8s !")
except Exception as e:
    ai_fog = None
    print(f"⚠️ Erreur de chargement de l'I.A ({e}). Mode basique 40-80 maintenu.")

# Initialisation Cloud/MLOps (Kafka Producer)
if KafkaProducer is not None:
    try:
        KAFKA_HOST = os.getenv('KAFKA_HOST', '192.168.100.97')  # IP de votre PC Windows
        kafka_producer = KafkaProducer(
            bootstrap_servers=[f'{KAFKA_HOST}:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"☁️ Connecté au Broker Kafka sur {KAFKA_HOST}:9092.")
    except Exception as e:
        kafka_producer = None
        print(f"⚠️ Serveur Kafka non détecté ({e}). Mode Local CSV maintenu.")
else:
    kafka_producer = None
    print("⚠️ Module 'kafka-python' non installé. Ignorer l'export Cloud.")

# En-tête STRICT du nouveau dataset (18 colonnes)
HEADERS = ['timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 'payload_bytes', 'rssi', 'snr', 
           'rtt_cloud_ms', 'decision_latency_ms', 'jitter_ms', 'missing_packets', 'cpu_percent', 
           'ram_percent', 'node_batt_pct', 'node_current_ma', 'gateway_batt_pct', 'gateway_current_ma']

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connecté au broker MQTT local (Code {rc})")
    client.subscribe("irrigation/soil/#")
    print("🎧 En écoute sur le topic : irrigation/soil/#")

def on_message(client, userdata, msg):
    try:
        node_id = msg.topic.split("/")[-1]
        payload = msg.payload.decode('utf-8', errors='ignore')
        data = json.loads(payload)
        
        # --- 1. EXTRACTION NORMALISÉE ET SÉCURISÉE ---
        # ✅ FIXE #1 : ISO timestamp au lieu d'Unix seconds
        timestamp = datetime.now().isoformat()  # Format ISO : "2026-04-14T17:19:56.123456"
        
        raw_string = data.get("raw", "")
        # ✅ FIXE #2 : Extraire TOUS les champs MQTT
        rssi = data.get("rssi", 0)
        snr = data.get("snr", 0)
        jitter_ms = data.get("jitter_ms", 0)
        missing_packets = data.get("missing_packets", 0)
        node_batt_pct = data.get("node_batt_pct", 0)
        node_current_ma = data.get("node_current_ma", 0)
        gateway_batt_pct = data.get("gateway_batt_pct", 0)
        gateway_current_ma = data.get("gateway_current_ma", 0)
        
        # NOUVEAU : Prêt à capturer la latence dynamique !
        decision_latency_ms = data.get("decision_latency_ms", "") 
        
        counter = ""
        soil_pct = ""
        # Décorticage propre de la trame radio brute envoyée par l'Arduino
        parts = raw_string.split(',')
        if len(parts) >= 4:
            counter = parts[1].strip()
            soil_pct = parts[3].strip() # Récupération directe de l'humidité
            
        # --- 2. SAUVEGARDE STRICTE AU FORMAT 18 COLONNES (APPEND) ---
        # Capture de la santé système réelle
        cpu_p = psutil.cpu_percent() if psutil else 0
        ram_p = psutil.virtual_memory().percent if psutil else 0
        
        # ✅ FIXE #2 : Remplir TOUS les 18 champs correctement
        row = [
            timestamp,              # [1] ISO timestamp (fixé)
            node_id,                # [2] node1 ou node2
            counter,                # [3] counter (vient du raw_string)
            soil_pct,               # [4] humidité %
            raw_string,             # [5] trame brute complète
            len(raw_string),        # [6] payload_bytes = longueur du payload
            rssi,                   # [7] signal strength (fixé)
            snr,                    # [8] signal-to-noise ratio (fixé)
            "",                     # [9] rtt_cloud_ms (vient du Kafka)
            decision_latency_ms,    # [10] latence IA FOG
            jitter_ms,              # [11] jitter (fixé)
            missing_packets,        # [12] paquets manquants (fixé)
            cpu_p,                  # [13] CPU %
            ram_p,                  # [14] RAM %
            node_batt_pct,          # [15] batterie Arduino (fixée)
            node_current_ma,        # [16] courant Arduino (fixé)
            gateway_batt_pct,       # [17] batterie Gateway
            gateway_current_ma      # [18] courant Gateway
        ]
        
        # Mode Append : On n'écrit les headers que si le fichier est vide ou inexistant
        file_exists = os.path.isfile(CSV_FILE) and os.path.getsize(CSV_FILE) > 0
        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(HEADERS)
            writer.writerow(row)
            
        print(f"[OK] 💾 Données loggées pour {node_id} (Humidité: {soil_pct}%, RSSI: {rssi}, Batterie: {node_batt_pct}%)")
        
        # =========================================================
        # --- 3. LOGIQUE D'ARROSAGE + IA (AVANT L'ENVOI KAFKA) ---
        # On calcule la décision de l'IA en premier, pour que le
        # Cloud reçoive la VRAIE décision et non un fallback 40/80.
        # =========================================================
        ai_decision = 0  # Valeur par défaut
        if len(parts) >= 4: 
            try:
                humidity_pct = int(soil_pct)
                node_key = node_id.lower() 
                
                if node_key not in valve_states:
                    valve_states[node_key] = "OFF"
                    
                # --- CALCUL DE L'INERTIE FOG ---
                soil_diff = 0.0
                if last_humidity.get(node_key) is not None:
                    soil_diff = float(humidity_pct - last_humidity[node_key])
                last_humidity[node_key] = humidity_pct
                
                # --- DÉTECTION A.I. (Coupe dès 65% grâce au Label Hacking) ---
                if ai_fog is not None:
                    features = np.array([[float(humidity_pct), soil_diff]])
                    ai_decision = int(ai_fog.predict(features)[0])  # 1=ARROSER, 0=COUPER
                else:
                    # Fallback sur l'ancien système (Security)
                    if humidity_pct < 40: ai_decision = 1
                    elif humidity_pct >= 65: ai_decision = 0  # On garde la logique 65% du Label Hacking
                    else: ai_decision = 1 if valve_states[node_key] == "ON" else 0
                
                # FOG : Commande d'allumage paramétrée par l'IA
                if ai_decision == 1 and valve_states[node_key] == "OFF":
                    command = f"{node_key.upper()}_ON"
                    client.publish(TOPIC_CONTROL, command)
                    valve_states[node_key] = "ON"
                    print(f"   -> 🧠 FOG AI ACTION ({humidity_pct}% | inertie: {soil_diff:.1f}) : {command} envoyé !")
                    
                # FOG : Commande d'arrêt paramétrée par l'IA (Économie d'eau réelle !)
                elif ai_decision == 0 and valve_states[node_key] == "ON":
                    command = f"{node_key.upper()}_OFF"
                    client.publish(TOPIC_CONTROL, command)
                    valve_states[node_key] = "OFF"
                    print(f"   -> 🧠 FOG AI COUPE ({humidity_pct}% | inertie: {soil_diff:.1f}) : {command} (Économie eau!)")
                    
            except ValueError:
                pass
        
        # --- 4. EXPORT KAFKA (VERS GRAFANA / DATAOPS) ---
        # Important : On envoie maintenant la vraie décision IA (ai_decision)
        # calculée juste au-dessus, et non un calcul hardcodé 40/80 !
        if kafka_producer is not None:
            try:
                soil_float = 0.0
                try:
                    soil_float = float(soil_pct)
                except:
                    pass
                kafka_payload = {
                    "timestamp": timestamp,
                    "node_id": node_id,
                    "soil_pct": soil_float,
                    "irrigation_status": ai_decision,
                    "decision_latency_ms": float(decision_latency_ms) if decision_latency_ms != "" else 0.0,
                    "rssi": int(rssi) if rssi != "" else 0,
                    "snr": float(snr) if snr != "" else 0.0,
                    "gateway_batt_pct": float(gateway_batt_pct) if gateway_batt_pct != "" else 100.0,
                    "cpu_percent": cpu_p,
                    "ram_percent": ram_p
                }
                kafka_producer.send("iot_smart_irrigation", kafka_payload)
            except Exception as k_err:
                pass  # Erreur silencieuse : le FOG ne doit jamais crasher à cause du Cloud

    except Exception as e:
        print(f"❌ Erreur lors du traitement du message: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Configuration du broker local (Raspberry)
client.connect("localhost", 1883, 60)

try:
    print("Démarrage du Data Logger en arrière-plan...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel.")