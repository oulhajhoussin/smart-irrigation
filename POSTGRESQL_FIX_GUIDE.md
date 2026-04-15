# 🔧 PostgreSQL Connection Fix for Streamlit

## 📋 PROBLÈME IDENTIFIÉ

### Erreur principale : 
Streamlit ne peut pas se connecter à PostgreSQL parce que :

1. **❌ IP incorrecte** : `app.py` tentait de se connecter à `192.168.100.97` (IP Raspberry Pi)
   - Mais PostgreSQL tourne dans **Docker** sur le Raspberry
   - Docker n'expose PAS sa Postgres sur l'IP du Raspberry
   - La connexion doit se faire via `localhost` (127.0.0.1)

2. **❌ Port en string** : `"port": "5432"` au lieu de `"port": 5432`
   - psycopg2 attend un entier, pas une string

3. **❌ Mauvaise gestion du fallback** : Si PostgreSQL échouait, Streamlit restait bloqué
   - Pas d'affichage clair du mode secours CSV

---

## ✅ SOLUTIONS APPLIQUÉES

### 1. Correction de la configuration PostgreSQL
```python
# AVANT (Mauvais)
DB_CONFIG = {"host": "192.168.100.97", "port": "5432", ...}

# APRÈS (Correct)
DB_CONFIG = {
    "host": "localhost",  # Docker interne au Pi
    "database": "airflow",
    "user": "airflow",
    "password": "airflow",
    "port": 5432,  # Type int
    "connect_timeout": 3
}
```

### 2. Amélioration du fallback SQL → CSV
- Essayer la table `iot_smart_irrigation_raw` (nouvelle)
- Si elle n'existe pas → essayer `raw_soil_moisture` (ancienne)
- Si PostgreSQL échoue → passer automatiquement au CSV local
- Message clair dans la sidebar indiquant le mode actif

### 3. Ajout du diagnostic dans l'interface
- Sidebar affiche maintenant l'état réel (Cloud SQL vs Local CSV)
- Section de débogage (🔧) pour voir les chemins et status

### 4. Création d'un script de diagnostic
- `diagnose_postgres.py` pour tester la connexion
- Vérifie psycopg2, Postgres, tables, et CSV

---

## 📍 ÉTAPES À SUIVRE SUR LE RASPBERRY PI

### Étape 1 : Transférer les fichiers mis à jour
```bash
# Sur le Pi :
# Utilisez FileZilla ou SCP pour copier :
scp app.py pi@192.168.100.66:/home/pi/
scp diagnose_postgres.py pi@192.168.100.66:/home/pi/
```

### Étape 2 : Vérifier la connexion PostgreSQL
```bash
# Sur le Pi :
cd /home/pi
python3 diagnose_postgres.py
```

**Résultats attendus** :
```
✅ psycopg2 is installed
✅ Connected to PostgreSQL!
✅ Found tables in 'airflow' database
✅ iot_smart_irrigation_raw table exists (N rows)
✅ CSV file exists
```

### Étape 3 : Installer psycopg2 si manquant
```bash
pip3 install psycopg2-binary
```

### Étape 4 : Redémarrer Streamlit
```bash
# Tuer l'ancienne instance
pkill -f "streamlit run app.py"

# Relancer
streamlit run app.py
```

---

## 🧪 TEST DES DEUX MODES

### Mode 1 : PostgreSQL Actif (Normal)
- Streamlit affiche "Cloud (SQL)" dans la sidebar
- Les données viennent de la table `iot_smart_irrigation_raw`
- Grafana et Streamlit voient les mêmes données en temps réel

### Mode 2 : PostgreSQL Offline (Secours)
- Arrêtez Docker : `docker compose down`
- Relancez Streamlit
- Il affiche "Local (CSV) - Mode Secours 🛡️"
- Les graphes continuent de fonctionner depuis le CSV local
- **Avantage** : Aucune interruption du monitoring, même en cas de panne réseau

```bash
# Pour tester :
docker compose down
# Streamlit bascule automatiquement en mode CSV
docker compose up -d
# Streamlit revient en mode PostgreSQL
```

---

## 🔗 ARCHITECTURE COMPLÈTE

```
┌─────────────────────────────────────────────────┐
│         CAPTEURS IoT (LoRa)                     │
│     Node1 + Node2 → TTGO ESP32                  │
└─────────────────────┬───────────────────────────┘
                      │ (MQTT local)
┌─────────────────────▼───────────────────────────┐
│    Raspberry Pi (Fog Gateway)                   │
│  ┌────────────────────────────────────────┐     │
│  │ data_logger.py                         │     │
│  │ ├─ Reçoit les données du TTGO (MQTT)  │     │
│  │ ├─ Envoie à Kafka                      │     │
│  │ └─ Sauvegarde localement (CSV)         │     │
│  └────────────┬──────────────────────────┘     │
│               │                                 │
│      ┌────────┴──────────┐                      │
│      │                   │                      │
│  ┌───▼────┐          ┌──▼──────┐                │
│  │ Kafka  │          │CSV Local│                │
│  └───┬────┘          └──┬──────┘                │
│      │                  │                       │
│  ┌───▼──────────────────▼──┐                    │
│  │   app.py (Streamlit)    │                    │
│  │  • Tente Postgres/SQL   │                    │
│  │  • Fallback CSV si panne│                    │
│  └────────────────────────┘                    │
└─────────────────────┬───────────────────────────┘
                      │ (si Kafka OK)
        ┌─────────────┴──────────────┐
        │                            │
┌───────▼────────┐        ┌──────────▼────┐
│  Docker Stack  │        │ Grafana Cloud │
│ ┌────────────┐ │        │   (si actif)   │
│ │ PostgreSQL │ │        └────────────────┘
│ │ Kafka      │ │
│ │ Grafana    │ │
│ │ MLflow     │ │
│ └────────────┘ │
└────────────────┘
```

---

## ⚙️ FICHIERS MODIFIÉS

| Fichier | Changement |
|---------|-----------|
| `app.py` | IP PostgreSQL : `192.168.100.97` → `localhost`<br>Port : `"5432"` → `5432`<br>Meilleur fallback CSV<br>Diagnostic dans sidebar |
| `diagnose_postgres.py` | **NOUVEAU** - Script de test de connexion |

---

## 🚨 TROUBLESHOOTING

### "Connection refused"
```bash
# Vérifier que Docker tourne
docker compose ps

# Vérifier les logs Postgres
docker compose logs postgres --tail=20
```

### "Database 'airflow' does not exist"
```bash
# Redémarrer avec volume clean
docker compose down -v
docker compose up -d --build
```

### "psycopg2 not installed"
```bash
pip3 install psycopg2-binary
```

### "CSV file not found"
```bash
# S'assurer que data_logger.py tourne
ps aux | grep data_logger.py

# Si absent, lancer
python3 data_logger.py &
```

---

## ✅ RÉSULTAT FINAL

Après ces modifications, Streamlit doit :
1. ✅ Se connecter à PostgreSQL sur localhost:5432
2. ✅ Afficher les données en temps réel depuis Postgres (mode Cloud)
3. ✅ Basculer automatiquement au CSV si Postgres est hors ligne (mode Secours)
4. ✅ Afficher clairement le mode actif dans la sidebar
5. ✅ Continuer de fonctionner en toute circonstance

**Bon diagnostic ! 🔍**
