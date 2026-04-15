import pandas as pd
import os
import glob
from datetime import datetime

# --- CONFIGURATION ---
TARGET_FILE = r'c:\Users\GODFATHER\Desktop\dataset\codes\data_logger.csv'
MASTER_HEADERS = [
    'timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 
    'payload_bytes', 'rssi', 'snr', 'rtt_cloud_ms', 'decision_latency_ms', 
    'jitter_ms', 'missing_packets', 'cpu_percent', 'ram_percent', 
    'node_batt_pct', 'node_current_ma', 'gateway_batt_pct', 'gateway_current_ma'
]

def to_unix(ts_str):
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S').timestamp()
    except:
        return ts_str

def merge_datasets():
    print("[INFO] Demarrage de la consolidation des donnees...")
    all_dfs = []

    # 1. Dataset principal deja formate
    path_main = r'c:\Users\GODFATHER\Desktop\dataset\dataset_normalized.csv'
    if os.path.exists(path_main):
        print(f"[INFO] Lecture de {os.path.basename(path_main)}...")
        df = pd.read_csv(path_main)
        all_dfs.append(df)

    # 2. Donnees capteurs (Format different)
    path_capteurs = r'c:\Users\GODFATHER\Desktop\dataset\anciens_fichiers\donnees_capteurs.csv'
    if os.path.exists(path_capteurs):
        print(f"[INFO] Lecture de {os.path.basename(path_capteurs)} (Mappage en cours)...")
        df = pd.read_csv(path_capteurs)
        df_new = pd.DataFrame(columns=MASTER_HEADERS)
        df_new['timestamp'] = df['Timestamp'].apply(to_unix)
        df_new['node_id'] = df['Node']
        df_new['raw_data'] = df['Raw_Data']
        df_new['rssi'] = df['RSSI']
        df_new['snr'] = df['SNR']
        df_new['gateway_batt_pct'] = df['Batt_Pct']
        df_new['gateway_current_ma'] = df['Current_mA']
        all_dfs.append(df_new)

    # 3. Archives Thingsboard
    things_files = glob.glob(r'c:\Users\GODFATHER\Desktop\dataset\anciens_fichiers\*_thingsboard_*.csv')
    for f in things_files:
        print(f"[INFO] Lecture de {os.path.basename(f)}...")
        df = pd.read_csv(f)
        df_new = pd.DataFrame(columns=MASTER_HEADERS)
        for col in df.columns:
            if col in MASTER_HEADERS:
                df_new[col] = df[col]
        all_dfs.append(df_new)

    if not all_dfs:
        print("[ERROR] Aucune donnee trouvee.")
        return

    # Fusion et Nettoyage
    print("[INFO] Fusion des DataFrames...")
    master_df = pd.concat(all_dfs, ignore_index=True)
    
    # Tri par timestamp
    master_df['timestamp'] = pd.to_numeric(master_df['timestamp'], errors='coerce')
    master_df = master_df.dropna(subset=['timestamp']).sort_values('timestamp')
    
    # Suppression des doublons
    initial_len = len(master_df)
    master_df = master_df.drop_duplicates(subset=['timestamp', 'node_id'])
    print(f"[INFO] Nettoyage termine : {initial_len - len(master_df)} doublons supprimes.")

    # Sauvegarde
    os.makedirs(os.path.dirname(TARGET_FILE), exist_ok=True)
    master_df.to_csv(TARGET_FILE, index=False)
    print(f"[SUCCESS] Master Dataset cree avec succes : {TARGET_FILE} ({len(master_df)} lignes)")

if __name__ == "__main__":
    merge_datasets()
