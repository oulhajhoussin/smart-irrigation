import pandas as pd
import numpy as np
import joblib
import os
import psycopg2
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from micromlgen import port
from datetime import datetime

# --- CONFIGURATION MLOPS ---
MLFLOW_TRACKING_URI = "http://192.168.100.97:5000"
DB_CONFIG = {
    "host": "192.168.100.97", "database": "airflow", "user": "airflow", "password": "airflow", "port": "5432"
}
EXPERIMENT_NAME = "Smart_Irrigation_Hybrid"
MODEL_NAME_FOG = "SmartIrrigation_Fog"

# Initialisation MLflow
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(EXPERIMENT_NAME)

def train_and_log():
    print(f"[{datetime.now()}] 🚀 Démarrage du pipeline MLOps...")
    
    # 1. Extraction PostgreSQL (Source Unique)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT timestamp, node_id, humidity, irrigation_status FROM iot_smart_irrigation_raw"
        df = pd.read_sql(query, conn)
        conn.close()
        print(f"📊 Données extraites : {len(df)} lignes.")
    except Exception as e:
        print(f"❌ Erreur DB: {e}")
        return

    if df.empty or len(df) < 50:
        print("⚠️ Données insuffisantes pour l'entraînement.")
        return

    # 2. Pre-processing & Feature Engineering
    df = df.sort_values(by=['node_id', 'timestamp']).reset_index(drop=True)
    df['soil_pct_diff'] = df.groupby('node_id')['humidity'].diff().fillna(0)
    
    # Label Hacking (Contrainte métier : Arret à 65%)
    df['label_ai'] = df['irrigation_status'].copy()
    df.loc[(df['label_ai'] == 1) & (df['humidity'] >= 65), 'label_ai'] = 0
    df.loc[(df['label_ai'] == 1) & (df['soil_pct_diff'] > 1.5), 'label_ai'] = 0

    features = ['humidity', 'soil_pct_diff']
    X = df[features]
    y = df['label_ai']

    # 3. Entraînement avec MLflow Tracking
    with mlflow.start_run() as run:
        params = {"n_estimators": 10, "max_depth": 5, "random_state": 42}
        mlflow.log_params(params)
        
        clf = RandomForestClassifier(**params, class_weight='balanced')
        clf.fit(X.values, y.values)
        
        accuracy = clf.score(X.values, y.values)
        mlflow.log_metric("accuracy", accuracy)
        print(f"✅ Modèle entraîné (Accuracy: {accuracy:.2%})")

        # 4. Génération des Artefacts
        # Fog Model (.pkl)
        fog_path = "fog_brain.pkl"
        joblib.dump(clf, fog_path)
        mlflow.log_artifact(fog_path, artifact_path="models_fog")
        
        # TinyML Model (.h)
        edge_path = "tinyml_edge_brain.h"
        try:
            c_code = port(clf)
            with open(edge_path, "w") as f: f.write(c_code)
            mlflow.log_artifact(edge_path, artifact_path="models_edge")
            print("💎 Header TinyML généré.")
        except Exception as e:
            print(f"⚠️ Erreur TinyML: {e}")

        # 5. Enregistrement dans le Registry
        model_uri = f"runs:/{run.info.run_id}/models_fog"
        mlflow.sklearn.log_model(clf, "model", registered_model_name=MODEL_NAME_FOG)
        
        print(f"🏁 Pipeline terminé. Run ID: {run.info.run_id}")

if __name__ == "__main__":
    train_and_log()
