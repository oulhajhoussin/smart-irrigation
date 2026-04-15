import pandas as pd
import numpy as np
import os

input_file = r'c:\Users\GODFATHER\Desktop\dataset\dataset_normalized.csv'
output_file = r'c:\Users\GODFATHER\Desktop\dataset\dataset_ml_ready.csv'

print("Chargement du dataset normalisé...")
df = pd.read_csv(input_file)

# 1. Sélection des features utiles
# D'après la remarque: Les batteries sont sur secteur, on les élimine pour éviter le bruit au ML.
columns_to_keep = ['timestamp', 'node_id', 'soil_pct', 'rssi']
df = df[columns_to_keep]

print("Traitement des valeurs manquantes et chronologie...")
# 2. Tri chronologique crucial pour Hystérésis et Forward-Fill
df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])
df = df.sort_values(by=['timestamp', 'node_id'])

# 3. Traitement des NaNs (Forward Fill par noeud)
# On applique un remplissage en avant (ffill) sur l'humidité et le rssi car ce sont des données continues
df[['soil_pct', 'rssi']] = df.groupby('node_id')[['soil_pct', 'rssi']].ffill()

# On supprime ce qui reste vide au tout début (avant le premier relevé)
df = df.dropna(subset=['soil_pct', 'rssi'])

# 4. Suppression des doublons (Même temps, même noeud)
initial_len = len(df)
df = df.drop_duplicates(subset=['timestamp', 'node_id'])
print(f"{initial_len - len(df)} doublons supprimés.")

print("Génération de la Cible (Le Label IA)...")
# 5. Création de la Variable Cible (Label) avec l'algorithme d'Hystérésis
def simulate_pump(hum_series):
    states = []
    pump_state = 0
    for h in hum_series:
        if pd.isna(h):
            states.append(pump_state)
            continue
        if h < 40:
            pump_state = 1
        elif h >= 80:
            pump_state = 0
        states.append(pump_state)
    return states

df['label_pompe'] = 0

for node in df['node_id'].unique():
    mask = df['node_id'] == node
    df.loc[mask, 'label_pompe'] = simulate_pump(df.loc[mask, 'soil_pct'])

# 6. Sauvegarde du fichier propre
df.to_csv(output_file, index=False)
print(f"Nettoyage terminé avec SUCCÈS ! Dataset ML final : {len(df)} lignes sauvegardées dans {output_file}")
