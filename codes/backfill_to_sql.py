import pandas as pd
import psycopg2
from datetime import datetime
import time

# --- CONFIGURATION ---
CSV_PATH = r'codes/data_logger.csv'
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "airflow",
    "password": "airflow",
    "dbname": "airflow",
    "port": 5432
}

def backfill():
    print("[INFO] Demarrage de l'injection SQL (CSV -> PostgreSQL)...")
    
    # 1. Lecture du CSV
    try:
        df = pd.read_csv(CSV_PATH)
        print(f"[INFO] {len(df)} lignes chargees depuis le CSV.")
    except Exception as e:
        print(f"[ERROR] Impossible de lire le CSV: {e}")
        return

    # 2. Connexion DB
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("[INFO] Connecte a PostgreSQL.")
    except Exception as e:
        print(f"[ERROR] Echec de la connexion SQL: {e}")
        return

    # 3. Insertion par paquets (Batch) pour la performance
    print("[INFO] Injection en cours (cela peut prendre 30s)...")
    
    # On vide la table pour avoir une presentation propre (Optionnel, demandez si besoin)
    # cur.execute("DELETE FROM iot_smart_irrigation_raw") 

    count = 0
    batch_size = 1000
    records = []

    for _, row in df.iterrows():
        ts = datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        status = 1 if "ON" in str(row['raw_data']) else 0
        
        records.append((
            ts, 
            row['node_id'], 
            float(row['soil_pct']), 
            status, 
            float(row['decision_latency_ms']), 
            int(row['rssi']), 
            float(row['gateway_batt_pct'])
        ))
        
        if len(records) >= batch_size:
            cur.executemany("""
                INSERT INTO iot_smart_irrigation_raw 
                (timestamp, node_id, humidity, irrigation_status, decision_latency_ms, rssi, gateway_batt_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, records)
            conn.commit()
            records = []
            count += batch_size
            if count % 50000 == 0:
                print(f"[PROGRESS] {count} lignes inserees...")

    # Dernier batch
    if records:
        cur.executemany("""
            INSERT INTO iot_smart_irrigation_raw 
            (timestamp, node_id, humidity, irrigation_status, decision_latency_ms, rssi, gateway_batt_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, records)
        conn.commit()

    print(f"[SUCCESS] Injection terminee ! {len(df)} lignes synchronisees.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    backfill()
