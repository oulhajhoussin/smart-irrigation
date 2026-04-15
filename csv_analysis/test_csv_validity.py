#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🧪 CSV VALIDATION TEST
Vérifie que le CSV est lisible et contient les bonnes données
"""

import pandas as pd
import os
from datetime import datetime

CSV_FILE = "/home/pi/data_logger.csv"
HEADERS_CSV = ['timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 'payload_bytes', 
               'rssi', 'snr', 'rtt_cloud_ms', 'decision_latency_ms', 'jitter_ms', 'missing_packets', 
               'cpu_percent', 'ram_percent', 'node_batt_pct', 'node_current_ma', 'gateway_batt_pct', 'gateway_current_ma']

def test_csv():
    print("\n" + "="*60)
    print("🧪 CSV VALIDATION TEST")
    print("="*60)
    
    # Test 1 : Fichier existe
    print("\n[TEST 1] Vérifier fichier...")
    if not os.path.exists(CSV_FILE):
        print(f"❌ FAIL : CSV n'existe pas : {CSV_FILE}")
        return False
    print(f"✅ PASS : CSV trouvé ({os.path.getsize(CSV_FILE)} bytes)")
    
    # Test 2 : Fichier pas vide
    if os.path.getsize(CSV_FILE) == 0:
        print("❌ FAIL : CSV vide (0 bytes)")
        return False
    print(f"✅ PASS : CSV contient des données")
    
    # Test 3 : Lire le CSV avec pandas
    print("\n[TEST 2] Lire CSV...")
    try:
        # Essayer avec parse_dates (nouveau format ISO)
        df = pd.read_csv(CSV_FILE, names=HEADERS_CSV, 
                        dtype={'raw_data': str, 'node_id': str},
                        parse_dates=['timestamp']).tail(100)
        print(f"✅ PASS : CSV lu avec succès ({len(df)} lignes)")
    except Exception as e:
        print(f"⚠️ WARN : Lecture avec parse_dates échoue : {e}")
        print("   → Essai sans parse_dates...")
        try:
            df = pd.read_csv(CSV_FILE, names=HEADERS_CSV, 
                            dtype={'raw_data': str, 'node_id': str}).tail(100)
            print(f"✅ PASS : CSV lu sans parse_dates ({len(df)} lignes)")
        except Exception as e2:
            print(f"❌ FAIL : Impossible de lire le CSV : {e2}")
            return False
    
    # Test 4 : Vérifier colonnes
    print("\n[TEST 3] Vérifier structure...")
    print(f"Colonnes trouvées : {len(df.columns)}")
    print(f"Attendu : {len(HEADERS_CSV)}")
    
    if len(df.columns) != len(HEADERS_CSV):
        print(f"⚠️ WARN : Nombre de colonnes incorrect")
    else:
        print("✅ PASS : Nombre de colonnes correct")
    
    # Test 5 : Vérifier contenu
    print("\n[TEST 4] Vérifier contenu...")
    print("\nPremières lignes du CSV :")
    print("-" * 100)
    print(df.head(3).to_string())
    print("-" * 100)
    
    # Test 6 : Vérifier timestamps
    print("\n[TEST 5] Vérifier timestamps...")
    if df.empty:
        print("⚠️ WARN : DataFrame vide (pas de données)")
    else:
        first_ts = df['timestamp'].iloc[0]
        print(f"Premier timestamp : {first_ts}")
        print(f"Type : {type(first_ts)}")
        
        # Vérifier format
        try:
            ts_str = str(first_ts)
            if "2026" in ts_str or "2025" in ts_str or "T" in ts_str:
                print("✅ PASS : Timestamp semble au format ISO ou lisible")
            else:
                print(f"⚠️ WARN : Timestamp format inattendu : {ts_str}")
        except:
            print("⚠️ WARN : Impossible de vérifier format timestamp")
    
    # Test 7 : Vérifier champs non-vides
    print("\n[TEST 6] Vérifier champs remplis...")
    important_cols = ['timestamp', 'node_id', 'soil_pct', 'rssi', 'gateway_batt_pct']
    for col in important_cols:
        if col in df.columns:
            non_empty = df[col].notna().sum()
            total = len(df)
            pct = (non_empty / total * 100) if total > 0 else 0
            status = "✅" if pct > 50 else "⚠️"
            print(f"{status} {col}: {non_empty}/{total} ({pct:.0f}%)")
        else:
            print(f"❌ {col}: MANQUANTE")
    
    # Test 8 : Statistiques
    print("\n[TEST 7] Statistiques...")
    print(f"Total lignes CSV : {len(df)}")
    print(f"Nodes détectés : {df['node_id'].unique().tolist() if 'node_id' in df.columns else 'N/A'}")
    
    if 'soil_pct' in df.columns:
        soil_values = pd.to_numeric(df['soil_pct'], errors='coerce').dropna()
        if len(soil_values) > 0:
            print(f"Humidité moyenne : {soil_values.mean():.1f}%")
            print(f"Humidité min : {soil_values.min():.1f}% / max : {soil_values.max():.1f}%")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLET - CSV est lisible et contient des données")
    print("="*60 + "\n")
    return True

if __name__ == "__main__":
    try:
        success = test_csv()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE : {e}\n")
        exit(2)
