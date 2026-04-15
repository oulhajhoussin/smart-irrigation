import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from micromlgen import port
import os

print("[1/4] Chargement du Dataset Mère...")
csv_path = "../dataset_ml_ready.csv"
if not os.path.exists(csv_path):
    csv_path = "dataset_ml_ready.csv" # Fallback
    
df = pd.read_csv(csv_path)
print(f"   Shape: {df.shape}")

print("[2/4] Ingenierie des Caracteristiques (Feature Engineering)...")
# Tri chronologique obligatoire pour calculer l'inertie
df = df.sort_values(by=['node_id', 'timestamp']).reset_index(drop=True)

# 1. Calcul de l'Inertie du Sol (Dérivée) : Vitesse de mouillage/séchage
# On regarde l'Hymidité(t) moins l'Humidité(t-1)
df['soil_pct_diff'] = df.groupby('node_id')['soil_pct'].diff().fillna(0)

# 2. Le Hacking Biologique (Label Falsification pour économiser l'eau)
print("Ajout de la contrainte d'economie d'eau (Arret a 65%)...")
df['label_ai'] = df['label_pompe'].copy()

# Règle A : Ne jamais pomper si le sol est au dessus de 65% (L'A.I. anticipe la capillarité)
df.loc[(df['label_ai'] == 1) & (df['soil_pct'] >= 65), 'label_ai'] = 0

# Règle B : Ne pas pomper si le sol boit déjà intensément l'eau (Vitesse > +1.5% par tick)
df.loc[(df['label_ai'] == 1) & (df['soil_pct_diff'] > 1.5), 'label_ai'] = 0

print("[3/4] Entrainement de l'A.I. Random Forest...")
# Les deux seules variables que l'ESP32 aura en plein milieu du désert sans internet
features = ['soil_pct', 'soil_pct_diff']

X = df[features]
y = df['label_ai']

# On bride volontairement l'IA (10 arbres, profondeur 5) pour qu'elle puisse 
# tenir physiquement dans la toute petite RAM de l'ESP32 TTGO !
clf = RandomForestClassifier(n_estimators=10, max_depth=5, random_state=42, class_weight='balanced')
clf.fit(X.values, y.values)

score = clf.score(X.values, y.values)
print(f"   Accuracy d'apprentissage : {score*100:.2f}%")

print("[4/4] Deploiement : L'Intelligence Artificielle Distribuee !")

# EXPORT FOG (Raspberry Pi)
fog_path = "fog_brain.pkl"
joblib.dump(clf, fog_path)
print(f"   OK -> Cerveau FOG genere : '{fog_path}' (Pour data_logger.py)")

# EXPORT EDGE (TTGO µController)
edge_path = "tinyml_edge_brain.h"
c_code = port(clf)
with open(edge_path, "w", encoding="utf-8") as f:
    f.write(c_code)
print(f"   OK -> Cerveau EDGE genere : '{edge_path}' (Pour Code C++)")

print("\nSUCCES TOTAL : Les deux cerveaux jumeaux sont prets a etre reveilles.")
