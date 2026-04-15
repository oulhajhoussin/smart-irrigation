import pandas as pd
import numpy as np
import os
import psycopg2
from datetime import datetime, timedelta

# --- CONFIGURATION ---
CSV_PATH = r'codes/data_logger.csv'
DB_CONFIG = {"host": "127.0.0.1", "user": "airflow", "password": "airflow", "dbname": "airflow", "port": 5432}
TIME_STEP_SEC = 30 # Un paquet toutes les 30s

def catchup():
    print("[INFO] Demarrage du rattrapage de donnees (Catch-up)...")
    
    # 1. Recuperation du dernier point
    if not os.path.exists(CSV_PATH):
        print("[ERROR] CSV introuvable. Rien a rattraper.")
        return
    
    df_old = pd.read_csv(CSV_PATH)
    last_ts = df_old['timestamp'].max()
    start_time = datetime.fromtimestamp(last_ts)
    end_time = datetime.now()
    
    if (end_time - start_time).total_seconds() < 60:
        print("[INFO] Le dataset est deja a jour.")
        return

    print(f"[INFO] Rattrapage de {start_time} a {end_time}...")
    
    # 2. Generation de la simulation manquante
    all_data = []
    nodes = {
        'node1': {'hum': 51.0, 'pump': False, 'type': 'IA', 'cutoff': 65, 'counter': 200000},
        'node2': {'hum': 46.0, 'pump': False, 'type': 'Naive', 'cutoff': 80, 'counter': 200000}
    }

    current_time = start_time + timedelta(seconds=TIME_STEP_SEC)
    while current_time < end_time:
        hour = current_time.hour
        evap_rate = 0.005 if (10 <= hour <= 18) else 0.002
        
        for nid, state in nodes.items():
            if state['pump']:
                state['hum'] += 0.25
                if state['hum'] >= state['cutoff']:
                    state['pump'] = False
                    state['hum'] += 2.0 
            else:
                state['hum'] -= evap_rate + np.random.uniform(0, 0.001)
                if state['hum'] <= 40.0:
                    state['pump'] = True
            
            state['hum'] = max(0, min(100, state['hum']))
            
            pump_str = "ON" if state['pump'] else "OFF"
            raw_data = f"{nid.upper()},{int(state['hum'])},{pump_str}"
            
            row = {
                'timestamp': current_time.timestamp(),
                'node_id': nid,
                'counter': state['counter'],
                'soil_pct': int(state['hum']),
                'raw_data': raw_data,
                'payload_bytes': 48,
                'rssi': -55 + np.random.randint(-5, 5),
                'snr': 11.5,
                'rtt_cloud_ms': 135.0,
                'decision_latency_ms': 45.0,
                'jitter_ms': 2.0,
                'missing_packets': 0,
                'cpu_percent': 1.5,
                'ram_percent': 3.8,
                'node_batt_pct': 90,
                'node_current_ma': 50.0 if state['pump'] else 0.0,
                'gateway_batt_pct': 92,
                'gateway_current_ma': 120.0
            }
            all_data.append(row)
            state['counter'] += 1
        current_time += timedelta(seconds=TIME_STEP_SEC)

    # 3. Mise a jour du CSV
    new_df = pd.DataFrame(all_data)
    final_df = pd.concat([df_old, new_df], ignore_index=True)
    final_df = final_df.sort_values('timestamp').drop_duplicates(subset=['timestamp', 'node_id'])
    final_df.to_csv(CSV_PATH, index=False)
    print(f"[SUCCESS] CSV Master mis a jour (+{len(new_df)} lignes).")

    # 4. Injection SQL Directe (Bypass network auth via Docker exec style logic or direct connection)
    print("[INFO] Injection des nouvelles donnees dans PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        records = []
        for _, r in new_df.iterrows():
            ts_sql = datetime.fromtimestamp(r['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            status = 1 if "ON" in str(r['raw_data']) else 0
            records.append((
                ts_sql, r['node_id'], float(r['soil_pct']), status, 
                float(r['decision_latency_ms']), int(r['rssi']), 
                float(r['gateway_batt_pct']), float(r['cpu_percent']), float(r['ram_percent'])
            ))
        
        cur.executemany("""
            INSERT INTO iot_smart_irrigation_raw (timestamp, node_id, humidity, irrigation_status, decision_latency_ms, rssi, gateway_batt_pct, cpu_percent, ram_percent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, records)
        conn.commit()
        print("[SUCCESS] SQL Cloud mis a jour.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARNING] SQL non mis a jour automatiquement: {e}")
        print("[TIP] Vous pouvez lancer l'injection SQL native manuellement si besoin.")

if __name__ == "__main__":
    catchup()
