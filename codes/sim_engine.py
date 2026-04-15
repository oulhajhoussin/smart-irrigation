import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TARGET_FILE = r'c:\Users\GODFATHER\Desktop\dataset\codes\data_logger.csv'
DURATION_DAYS = 30
TIME_STEP_SEC = 30  # Un paquet toutes les 30s
START_DATE = datetime.now() - timedelta(days=DURATION_DAYS)

HEADERS = [
    'timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 
    'payload_bytes', 'rssi', 'snr', 'rtt_cloud_ms', 'decision_latency_ms', 
    'jitter_ms', 'missing_packets', 'cpu_percent', 'ram_percent', 
    'node_batt_pct', 'node_current_ma', 'gateway_batt_pct', 'gateway_current_ma'
]

def simulate():
    print("[INFO] Lancement du moteur de simulation (30 jours)...")
    
    # Statistiques basiques pour le realisme (tirees de vos donnees)
    base_rssi = -55
    base_snr = 11.5
    
    all_data = []
    
    # Etat initial des deux noeuds
    nodes = {
        'node1': {'hum': 60.0, 'pump': False, 'type': 'IA', 'cutoff': 65, 'counter': 1000},
        'node2': {'hum': 50.0, 'pump': False, 'type': 'IA', 'cutoff': 65, 'counter': 1000}
    }

    current_time = START_DATE
    total_steps = int((DURATION_DAYS * 24 * 3600) / TIME_STEP_SEC)

    print(f"[INFO] Generation de {total_steps} etapes (x2 noeuds)...")

    for i in range(total_steps):
        hour = current_time.hour
        
        # 1. EVAPORATION : Plus forte le jour (10h-18h)
        evap_rate = 0.005 if (10 <= hour <= 18) else 0.002
        
        for nid, state in nodes.items():
            # Physique du sol
            if state['pump']:
                # ABSORPTION : L'humidite monte vite si la pompe est ON
                state['hum'] += 0.25 # ~30% par heure
                if state['hum'] >= state['cutoff']:
                    state['pump'] = False
                    # On ajoute un petit boost d'inertie (infiltration apres arret)
                    state['hum'] += 2.0 
            else:
                # EVAPORATION
                state['hum'] -= evap_rate + np.random.uniform(0, 0.001)
                if state['hum'] <= 40.0:
                    state['pump'] = True

            # Borner l'humidite
            state['hum'] = max(0, min(100, state['hum']))
            
            # 2. GENERATION DU PAQUET (Format 18 colonnes)
            ts_unix = current_time.timestamp()
            rssi = base_rssi + np.random.normal(0, 2)
            snr = base_snr + np.random.normal(0, 1)
            
            # Raw Data simul\u00e9
            pump_str = "ON" if state['pump'] else "OFF"
            raw_data = f"{nid.upper()},{int(state['hum'])},{pump_str}"
            
            row = {
                'timestamp': ts_unix,
                'node_id': nid,
                'counter': state['counter'],
                'soil_pct': int(state['hum']),
                'raw_data': raw_data,
                'payload_bytes': 48 + np.random.randint(0, 4),
                'rssi': round(rssi, 1),
                'snr': round(snr, 1),
                'rtt_cloud_ms': round(120 + np.random.uniform(0, 50), 2),
                'decision_latency_ms': round(42 + np.random.uniform(0, 5), 2),
                'jitter_ms': round(np.random.uniform(0, 10), 2),
                'missing_packets': 1 if np.random.random() < 0.01 else 0, # 1% de perte
                'cpu_percent': round(0.5 + np.random.uniform(0, 2), 1),
                'ram_percent': round(3.5 + np.random.uniform(0, 0.5), 1),
                'node_batt_pct': 90,
                'node_current_ma': 50.0 if state['pump'] else 0.0,
                'gateway_batt_pct': 92,
                'gateway_current_ma': 120.0
            }
            all_data.append(row)
            state['counter'] += 1

        # Avancement du temps
        current_time += timedelta(seconds=TIME_STEP_SEC)
        
        # Progress log lent
        if i % 20000 == 0 and i > 0:
            print(f"[PROGRESS] {int(i/total_steps*100)}% termines...")

    # Conversion en DataFrame
    new_df = pd.DataFrame(all_data)
    
    # 3. FUSION AVEC L'HISTORIQUE (Vrai Master File)
    if os.path.exists(TARGET_FILE):
        print("[INFO] Fusion avec le Master Dataset existant...")
        old_df = pd.read_csv(TARGET_FILE)
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    # Tri final et Sauvegarde
    final_df = final_df.sort_values('timestamp').drop_duplicates(subset=['timestamp', 'node_id'])
    final_df.to_csv(TARGET_FILE, index=False)
    
    print(f"[SUCCESS] Simulation terminee : {TARGET_FILE}")
    print(f"[STATS] Total lignes final : {len(final_df)}")

if __name__ == "__main__":
    simulate()
