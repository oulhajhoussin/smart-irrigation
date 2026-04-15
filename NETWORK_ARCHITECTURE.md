# 🏗️ NETWORK ARCHITECTURE - Corrected

## 🌐 Votre Topologie Réelle

```
┌─────────────────────────────────────────────────────────────┐
│                    PC LOCAL (192.168.100.97)                │
│                    ─────────────────────────                │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Docker Desktop (Windows/Mac)                        │  │
│  │  ├─ PostgreSQL:13 (airflow DB)   :5432              │  │
│  │  ├─ Kafka Broker                 :9092              │  │
│  │  ├─ Grafana                      :3000              │  │
│  │  ├─ MLflow Server                :5000              │  │
│  │  └─ Airflow                      :8080              │  │
│  └──────────────────────────────────────────────────────┘  │
│       ↑                                                      │
│       │ Accessible via : 192.168.100.97:PORT               │
│       │                                                      │
└──────┼──────────────────────────────────────────────────────┘
       │
       │ WiFi (192.168.100.0/24)
       │ Gateway: 192.168.100.1
       │
       └──→ ┌─────────────────────────────────────────┐
           │  Raspberry Pi (192.168.100.66)          │
           │  ─────────────────────────────────       │
           │  - MQTT Broker (Local)                   │
           │  - data_logger.py (Kafka Producer)       │
           │  - Streamlit Dashboard                   │
           │  - CSV Fallback (/home/pi/data_logger.csv)
           │  - ML Model (fog_brain.pkl)              │
           └────────────────────┬────────────────────┘
                                 │
                    MQTT/LoRa/Serial
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
         ┌──────▼──────┐              ┌──────────▼───┐
         │  ESP32 TTGO  │              │   Arduino    │
         │  LoRa Module │              │   Nodes      │
         │  (Gateway)   │              │   (Sensors)  │
         └──────┬───────┘              └──────┬───────┘
                │                            │
         MQTT+LoRa                    Serial/LoRa
                │                            │
         ┌──────▴────────────────────────────▴─────┐
         │    IoT Field Network (LoRa 433MHz)      │
         │    - Soil Moisture Sensors              │
         │    - Temperature Probes                 │
         │    - Water Valve Controllers            │
         └────────────────────────────────────────┘
```

---

## 🔗 FLUX DE DONNÉES

### Mode Normal (PostgreSQL actif)

```
IoT Sensors
    ↓ (LoRa)
TTGO Gateway + Arduino Nodes
    ↓ (MQTT)
data_logger.py (Raspberry Pi)
    ↓ (Kafka)
PostgreSQL (Docker PC 192.168.100.97:5432)
    ↓ (SQL Query)
Streamlit Dashboard (Raspberry Pi:8501)
    ↓
Grafana Dashboard (192.168.100.97:3000)
```

### Mode Secours (PostgreSQL indisponible)

```
IoT Sensors
    ↓ (LoRa)
TTGO Gateway + Arduino Nodes
    ↓ (MQTT)
data_logger.py (Raspberry Pi)
    ├─ Kafka → PostgreSQL (FAIL ❌)
    │
    └─ CSV File (/home/pi/data_logger.csv) ✅
       ↓ (Local Read)
       Streamlit Dashboard (Mode Secours 🛡️)
       ↓
       Grafana (Indépendant, continue de fonctionner)
```

---

## 🎯 Configuration Streamlit (app.py)

### ✅ CORRECT POUR VOTRE TOPOLOGIE

```python
# PostgreSQL sur PC local (Docker)
DB_CONFIG = {
    "host": "192.168.100.97",      # 🔧 IP WiFi de votre PC
    "port": 5432,                   # Port PostgreSQL
    "database": "airflow",
    "user": "airflow",
    "password": "airflow",
    "connect_timeout": 3            # Timeout rapide
}

# Streamlit s'exécute sur Raspberry Pi
# Peut se connecter à PostgreSQL via IP WiFi du PC
```

### Pourquoi cette configuration fonctionne :

| Composant | Localisation | Accès depuis Pi |
|-----------|-------------|-----------------|
| PostgreSQL | Docker/PC | `192.168.100.97:5432` ✅ |
| Kafka | Docker/PC | `192.168.100.97:9092` ✅ |
| Grafana | Docker/PC | `192.168.100.97:3000` ✅ |
| Streamlit | Raspberry Pi | `localhost:8501` ou `192.168.100.66:8501` |
| CSV Fallback | Raspberry Pi | `/home/pi/data_logger.csv` |

---

## 🧪 VALIDATION DE CONNECTIVITÉ

### Depuis le Raspberry Pi, testez :

```bash
# 1. Vérifier que le PC est accessible
ping 192.168.100.97

# 2. Vérifier PostgreSQL
psql -h 192.168.100.97 -U airflow -d airflow -c "SELECT 1"

# 3. Vérifier Kafka
nc -zv 192.168.100.97 9092

# 4. Vérifier Grafana
curl http://192.168.100.97:3000

# 5. Vérifier CSV local
ls -la /home/pi/data_logger.csv
```

### Résultats attendus

```
✅ ping 192.168.100.97 → Response (PC connecté)
✅ psql → Connection successful (PostgreSQL OK)
✅ nc -zv → Connection succeeded (Kafka OK)
✅ curl → Grafana HTML (Grafana OK)
✅ ls -la → File exists (CSV OK)
```

---

## 📋 DIAGNOSTIC RÉSEAU

### Vérifier votre PC local :

```powershell
# Sur Windows PowerShell
ipconfig /all

# Cherchez "Wireless LAN adapter Wi-Fi"
# IPv4 Address: 192.168.100.97 ✅
# Subnet Mask: 255.255.255.0 ✅
# Gateway: 192.168.100.1 ✅
```

### Vérifier les ports Docker :

```bash
# Sur PC local
docker ps                  # Liste les conteneurs
docker port postgres       # Montre les ports exposés
netstat -ano | findstr :5432  # Windows
sudo lsof -i :5432       # Mac/Linux
```

### Résultat attendu :

```
CONTAINER ID   PORTS
abc123...      0.0.0.0:5432->5432/tcp   ← Accessible sur 192.168.100.97:5432
def456...      0.0.0.0:3000->3000/tcp   ← Grafana sur 192.168.100.97:3000
ghi789...      0.0.0.0:9092->9092/tcp   ← Kafka sur 192.168.100.97:9092
```

---

## 🚨 TROUBLESHOOTING

### Si Streamlit ne peut pas atteindre PostgreSQL

**Étape 1 : Vérifier l'IP**
```bash
# Sur Pi
ping 192.168.100.97
# Doit répondre ✅

# Sur PC local
ipconfig /all
# Cherchez l'adresse IPv4 confirmée
```

**Étape 2 : Vérifier Docker**
```bash
# Sur PC local
docker compose ps
# PostgreSQL doit être UP
```

**Étape 3 : Vérifier les ports**
```bash
# Sur PC local
docker compose logs postgres | tail -20
# Cherchez "listening on 0.0.0.0:5432"
```

**Étape 4 : Test de connectivité**
```bash
# Sur Pi
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='192.168.100.97',
        port=5432,
        database='airflow',
        user='airflow',
        password='airflow'
    )
    print('✅ Connecté à PostgreSQL')
    conn.close()
except Exception as e:
    print(f'❌ Erreur: {e}')
"
```

**Étape 5 : Mode Secours**
```bash
# Si tout échoue, vérifier CSV local
ls -la /home/pi/data_logger.csv

# Streamlit doit basculer automatiquement
streamlit run /home/pi/app.py
# Sidebar doit afficher "Local (CSV) - Mode Secours 🛡️"
```

---

## 📡 PORTS IMPORTANTS

| Service | Host | Port | Accès |
|---------|------|------|-------|
| PostgreSQL | PC (Docker) | 5432 | `psql -h 192.168.100.97 -U airflow` |
| Kafka | PC (Docker) | 9092 | `nc -zv 192.168.100.97 9092` |
| Grafana | PC (Docker) | 3000 | `http://192.168.100.97:3000` |
| MLflow | PC (Docker) | 5000 | `http://192.168.100.97:5000` |
| Airflow | PC (Docker) | 8080 | `http://192.168.100.97:8080` |
| Streamlit | Pi | 8501 | `http://192.168.100.66:8501` |
| MQTT | Pi | 1883 | `mosquitto_sub -h 192.168.100.66` |

---

## 🎯 CHECKLIST DÉPLOIEMENT

- [ ] Confirmer IP PC : `ipconfig /all` → 192.168.100.97 ✅
- [ ] Docker running sur PC : `docker compose ps` → All UP ✅
- [ ] PostgreSQL accessible : `psql -h 192.168.100.97 ...` → OK ✅
- [ ] Transfert app.py vers Pi : `scp app.py pi@192.168.100.66:/home/pi/` ✅
- [ ] Streamlit lancé : `streamlit run /home/pi/app.py` ✅
- [ ] Sidebar affiche "Cloud (SQL)" : Vérifier connexion ✅
- [ ] Test failover : `docker compose down` → Mode Secours 🛡️ ✅
- [ ] Test récupération : `docker compose up` → Back to Cloud ✅

---

**Architecture validée pour :**
- ✅ Docker sur PC local (192.168.100.97)
- ✅ Streamlit sur Raspberry Pi (192.168.100.66)
- ✅ Communication via WiFi 192.168.100.0/24
- ✅ Fallback CSV automatique
- ✅ Grafana indépendant
- ✅ Kafka + PostgreSQL côté PC

**Status** : 🚀 READY FOR DEPLOYMENT
