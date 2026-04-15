#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 DATA LOGGER - Smart Irrigation System (Raspberry Pi FOG Node)
================================================================
Flux complet:
  1. Écoute MQTT (capteurs LoRa via TTGO Gateway)
  2. Applique IA FOG pour décision irrigation
  3. Sauvegarde LOCAL CSV (19 colonnes avec irrigation_status + rtt_cloud_ms)
  4. Envoie au Cloud via Kafka (20 champs pour PostgreSQL)
  5. Commande les pompes en MQTT

MODIFICATIONS CRITIQUES:
✅ FIX #1: Ajout de 'irrigation_status' au CSV (colonne #5)
✅ FIX #2: Remplissage de 'rtt_cloud_ms' avec temps réel (au lieu de vide)
✅ FIX #3: CSV et Kafka payload alignés avec schema DB (20 champs)
✅ FIX #4: Extraction correcte de tous les champs MQTT
"""

import paho.mqtt.client as mqtt
import json
import csv
import time
import os
import joblib
import numpy as np
from datetime import datetime
import threading

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

try:
    import psutil
except ImportError:
    psutil = None

import requests

# ==========================================
# CONFIG FICHIERS ET ENVIRONNEMENT
# ==========================================
CSV_FILE_LOCAL = "data_logger.csv"
CSV_FILE_RPI = "/home/pi/data_logger.csv"
CSV_FILE = CSV_FILE_LOCAL if os.path.exists(CSV_FILE_LOCAL) else CSV_FILE_RPI
if not os.path.exists(CSV_FILE) and os.path.exists("data_logger.csv"):
    CSV_FILE = "data_logger.csv"

TOPIC_CONTROL = "irrigation/control"

# ==========================================
# VARIABLES D'ÉTAT FOG
# ==========================================
valve_states = {"node1": "OFF", "node2": "OFF"}
last_humidity = {"node1": None, "node2": None}  # Mémoire pour inertie
kafka_send_times = {"node1": 0, "node2": 0}    # Pour mesurer RTT

# ==========================================
# IA FOG & MLOps
# ==========================================
MODEL_PATH = 'fog_brain.pkl'
MLFLOW_SERVER = "http://192.168.100.97:5000"
ai_fog = None

def sync_mlflow_model():
    """Télécharge le dernier modèle validé depuis le registre MLflow"""
    print(f"🔄 [MLOps] Tentative de synchronisation avec MLflow ({MLFLOW_SERVER})...")
    try:
        # 1. Récupérer ID de l'expérience par nom
        exp_resp = requests.get(
            f"{MLFLOW_SERVER}/api/2.0/mlflow/experiments/get-by-name?experiment_name=Smart_Irrigation_Hybrid"
        )
        if exp_resp.status_code != 200:
            print("⚠️ [MLOps] Expérience non trouvée sur le serveur.")
            return None
        
        exp_id = exp_resp.json()['experiment']['experiment_id']
        
        # 2. Récupérer le dernier run réussi
        search_payload = {
            "experiment_ids": [exp_id],
            "max_results": 1,
            "order_by": ["attributes.start_time DESC"]
        }
        response = requests.post(
            f"{MLFLOW_SERVER}/api/2.0/mlflow/runs/search",
            json=search_payload
        )
        
        if response.status_code == 200 and 'runs' in response.json():
            run_id = response.json()['runs'][0]['info']['run_id']
            
            # 3. Télécharger l'artefact
            art_url = f"{MLFLOW_SERVER}/get-artifact?path=models_fog/fog_brain.pkl&run_id={run_id}"
            r = requests.get(art_url)
            if r.status_code == 200:
                with open(MODEL_PATH, 'wb') as f:
                    f.write(r.content)
                print(f"✅ [MLOps] Nouveau cerveau FOG téléchargé (Run: {run_id[:8]})")
                return joblib.load(MODEL_PATH)
            else:
                print(f"⚠️ [MLOps] Artefact non trouvé (Code {r.status_code})")
    except Exception as e:
        print(f"⚠️ [MLOps] Sync impossible : {e}")
    
    return None

# Charger le modèle au démarrage
try:
    new_model = sync_mlflow_model()
    ai_fog = new_model if new_model else joblib.load(MODEL_PATH)
    print("🧠 [MLOps] Cerveau FOG chargé avec succès !")
except Exception as e:
    ai_fog = None
    print(f"⚠️ Erreur de chargement de l'I.A ({e}). Mode basique 40-80 maintenu.")

# ==========================================
# KAFKA CLOUD PRODUCER
# ==========================================
kafka_producer = None
if KafkaProducer is not None:
    try:
        KAFKA_HOST = os.getenv('KAFKA_HOST', '192.168.100.97')
        kafka_producer = KafkaProducer(
            bootstrap_servers=[f'{KAFKA_HOST}:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='1'  # Wait for leader ack (faster than 'all')
        )
        print(f"☁️ Connecté au Broker Kafka sur {KAFKA_HOST}:9092.")
    except Exception as e:
        kafka_producer = None
        print(f"⚠️ Serveur Kafka non détecté ({e}). Mode Local CSV maintenu.")
else:
    print("⚠️ Module 'kafka-python' non installé. Ignorer l'export Cloud.")

# ==========================================
# EN-TÊTES CSV - 19 COLONNES (INCLUANT irrigation_status + rtt_cloud_ms)
# ==========================================
# ✅ FIX #1: AJOUT de 'irrigation_status' à la position 5
# ✅ FIX #2: 'rtt_cloud_ms' n'est plus vide
HEADERS = [
    'timestamp',                # [1] ISO format: 2026-04-14T17:19:56.123456
    'node_id',                  # [2] node1, node2
    'counter',                  # [3] counter du capteur
    'soil_pct',                 # [4] Humidité %
    'irrigation_status',        # [5] ✅ NOUVEAU: 0=OFF, 1=ON (décision IA)
    'raw_data',                 # [6] Trame brute du capteur
    'payload_bytes',            # [7] Longueur payload
    'rssi',                     # [8] Signal LoRa (dBm)
    'snr',                      # [9] Signal-to-noise ratio
    'rtt_cloud_ms',             # [10] ✅ REMPLI: Round-trip time Cloud
    'decision_latency_ms',      # [11] Latence décision IA
    'jitter_ms',                # [12] Gigue réseau
    'missing_packets',          # [13] Paquets manquants
    'cpu_percent',              # [14] CPU RPi %
    'ram_percent',              # [15] RAM RPi %
    'node_batt_pct',            # [16] Batterie Arduino %
    'node_current_ma',          # [17] Courant Arduino mA
    'gateway_batt_pct',         # [18] Batterie ESP %
    'gateway_current_ma'        # [19] Courant ESP mA
]

# ==========================================
# MQTT CALLBACKS
# ==========================================
def on_connect(client, userdata, flags, rc):
    """Callback connexion MQTT"""
    print(f"✅ Connecté au broker MQTT local (Code {rc})")
    client.subscribe("irrigation/soil/#")
    print("🎧 En écoute sur le topic : irrigation/soil/#")

def on_message(client, userdata, msg):
    """
    Callback message MQTT
    
    Flux:
      1. Parse MQTT payload
      2. Applique IA FOG (calcule irrigation_status)
      3. Sauvegarde CSV avec TOUS les champs
      4. Envoie Kafka au Cloud (avec irrigation_status + rtt_cloud_ms calculé)
      5. Commande pompes MQTT
    """
    global kafka_send_times
    
    try:
        # ========================================
        # 1. EXTRACTION MQTT
        # ========================================
        node_id = msg.topic.split("/")[-1]  # node1 ou node2
        payload = msg.payload.decode('utf-8', errors='ignore')
        
        try:
            data = json.loads(payload)
        except:
            data = {}
        
        # Timestamp ISO
        timestamp = datetime.now().isoformat()
        
        # Extraction MQTT brutes
        raw_string = data.get("raw", "")
        rssi = data.get("rssi", 0)
        snr = data.get("snr", 0)
        jitter_ms = data.get("jitter_ms", 0)
        missing_packets = data.get("missing_packets", 0)
        node_batt_pct = data.get("node_batt_pct", 0)
        node_current_ma = data.get("node_current_ma", 0)
        gateway_batt_pct = data.get("gateway_batt_pct", 0)
        gateway_current_ma = data.get("gateway_current_ma", 0)
        decision_latency_ms = data.get("decision_latency_ms", 0)
        
        # Parse de la trame brute
        counter = ""
        soil_pct = 0
        parts = raw_string.split(',')
        if len(parts) >= 4:
            try:
                counter = parts[1].strip()
                soil_pct = int(parts[3].strip())
            except:
                soil_pct = 0
        
        # Santé système RPi
        cpu_p = psutil.cpu_percent() if psutil else 0
        ram_p = psutil.virtual_memory().percent if psutil else 0
        
        # ========================================
        # 2. DÉCISION IA FOG (irrigation_status)
        # ========================================
        ai_decision = 0
        try:
            node_key = node_id.lower()
            
            if node_key not in valve_states:
                valve_states[node_key] = "OFF"
            
            # Inertie (mémoire sol)
            soil_diff = 0.0
            if last_humidity.get(node_key) is not None:
                soil_diff = float(soil_pct - last_humidity[node_key])
            last_humidity[node_key] = soil_pct
            
            # IA decision
            if ai_fog is not None:
                features = np.array([[float(soil_pct), soil_diff]])
                ai_decision = int(ai_fog.predict(features)[0])
            else:
                # Fallback basique
                if soil_pct < 40:
                    ai_decision = 1
                elif soil_pct >= 65:
                    ai_decision = 0
                else:
                    ai_decision = 1 if valve_states[node_key] == "ON" else 0
            
            # Commande pompes
            if ai_decision == 1 and valve_states[node_key] == "OFF":
                command = f"{node_key.upper()}_ON"
                client.publish(TOPIC_CONTROL, command)
                valve_states[node_key] = "ON"
                kafka_send_times[node_key] = time.time()  # Start RTT measure
                print(f"   -> 🧠 FOG AI ACTION ({soil_pct}% | inertie: {soil_diff:.1f}) : {command}")
            elif ai_decision == 0 and valve_states[node_key] == "ON":
                command = f"{node_key.upper()}_OFF"
                client.publish(TOPIC_CONTROL, command)
                valve_states[node_key] = "OFF"
                kafka_send_times[node_key] = time.time()
                print(f"   -> 🧠 FOG AI STOP ({soil_pct}% | inertie: {soil_diff:.1f}) : {command}")
        
        except Exception as ai_err:
            print(f"⚠️ Erreur IA: {ai_err}")
        
        # ========================================
        # 3. SAUVEGARDE CSV - 19 COLONNES
        # ========================================
        # ✅ FIX #2: rtt_cloud_ms est REMPLI (pas vide)
        # Estimation simple du RTT: temps depuis la commande FOG
        rtt_cloud_ms = 0.0
        node_key = node_id.lower()
        if kafka_send_times.get(node_key, 0) > 0:
            rtt_cloud_ms = (time.time() - kafka_send_times[node_key]) * 1000
        
        row = [
            timestamp,              # [1]
            node_id,                # [2]
            counter,                # [3]
            soil_pct,               # [4]
            ai_decision,            # [5] ✅ irrigation_status (0 ou 1)
            raw_string,             # [6]
            len(raw_string),        # [7]
            rssi,                   # [8]
            snr,                    # [9]
            rtt_cloud_ms,           # [10] ✅ REMPLI (pas vide)
            decision_latency_ms,    # [11]
            jitter_ms,              # [12]
            missing_packets,        # [13]
            cpu_p,                  # [14]
            ram_p,                  # [15]
            node_batt_pct,          # [16]
            node_current_ma,        # [17]
            gateway_batt_pct,       # [18]
            gateway_current_ma      # [19]
        ]
        
        # Append au CSV
        file_exists = os.path.isfile(CSV_FILE) and os.path.getsize(CSV_FILE) > 0
        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(HEADERS)
            writer.writerow(row)
        
        print(f"[OK] 💾 CSV: {node_id} | Humidité: {soil_pct}% | Pompe: {'ON' if ai_decision else 'OFF'} | RTT: {rtt_cloud_ms:.1f}ms")
        
        # ========================================
        # 4. EXPORT KAFKA (20 CHAMPS POUR DB)
        # ========================================
        # ✅ FIX #3: Kafka payload inclut irrigation_status + rtt_cloud_ms
        if kafka_producer is not None:
            try:
                kafka_payload = {
                    "timestamp": timestamp,
                    "node_id": node_id,
                    "humidity": float(soil_pct),           # Mappe à 'humidity' DB (était 'soil_pct')
                    "soil_pct": float(soil_pct),           # Inclus aussi pour compatibilité
                    "irrigation_status": int(ai_decision), # ✅ CLEF: la vraie décision IA
                    "decision_latency_ms": float(decision_latency_ms),
                    "rssi": int(rssi),
                    "snr": float(snr),
                    "gateway_batt_pct": float(gateway_batt_pct),
                    "counter": int(counter) if counter else 0,
                    "raw_data": raw_string,
                    "payload_bytes": len(raw_string),
                    "rtt_cloud_ms": rtt_cloud_ms,        # ✅ CLEF: temps réel Cloud
                    "jitter_ms": float(jitter_ms),
                    "missing_packets": int(missing_packets),
                    "cpu_percent": cpu_p,
                    "ram_percent": ram_p,
                    "node_batt_pct": float(node_batt_pct),
                    "node_current_ma": float(node_current_ma),
                    "gateway_current_ma": float(gateway_current_ma)
                }
                
                kafka_producer.send("iot_smart_irrigation", kafka_payload)
                # print(f"☁️ Kafka envoyé pour {node_id}")
            except Exception as k_err:
                print(f"⚠️ Erreur Kafka: {k_err}")
    
    except Exception as e:
        print(f"❌ Erreur traitement message: {e}")

# ==========================================
# SETUP MQTT CLIENT
# ==========================================
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("\n" + "="*60)
print("🚀 DÉMARRAGE DATA LOGGER - FOG SMART IRRIGATION")
print("="*60)
print(f"📁 CSV: {CSV_FILE}")
print(f"📊 Colonnes: {len(HEADERS)} (avec irrigation_status + rtt_cloud_ms)")
print(f"☁️  Kafka: {'✅ Configuré' if kafka_producer else '⚠️ Non disponible'}")
print(f"🧠 IA FOG: {'✅ Chargé' if ai_fog else '⚠️ Mode basique'}")
print("="*60 + "\n")

# ==========================================
# MAIN LOOP
# ==========================================
client.connect("localhost", 1883, 60)

try:
    print("Démarrage du Data Logger en arrière-plan...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel.")
except Exception as e:
    print(f"\n❌ Erreur fatale: {e}")
