# 🚨 QUICK DIAGNOSIS - PROBLÈMES RÉSUMÉS

## Le Problème en 30 Secondes

```
Grafana affiche "No data"  ← PostgreSQL vide (2 lignes stales)
                           ← Consumer ne reçoit rien
                           ← Kafka vide
                           ← data_logger_NEW.py n'envoie rien
                           ← kafka-python NOT INSTALLED on RPi 💥
```

---

## Problèmes Trouvés

### 🔴 PROBLÈME #1: KAFKA-PYTHON MANQUANT SUR RPi
```
Fichier: codes/data_logger_NEW.py ligne 36
try:
    from kafka import KafkaProducer  ← FAIL SI NON INSTALLÉ
except ImportError:
    KafkaProducer = None             ← kafka_producer = None!

Résultat: kafka_producer.send() est IGNORÉ (if check ligne 340)
Impact: ZÉRO messages envoyés à Kafka → PostgreSQL reste vide
```

**Solution immédiate**:
```bash
# Sur le RPi:
pip3 install kafka-python

# Redémarrer le script:
pkill -f data_logger
python3 data_logger_NEW.py &
```

---

### 🔴 PROBLÈME #2: TOPICS KAFKA N'EXISTENT PAS
```
Status avant: AUCUN topic iot_smart_irrigation
Status après: CRÉÉS MANUELLEMENT ✅

Mais: Consumer essaie s'abonner à topics qui n'existaient pas
→ 0 messages consommés
→ PostgreSQL reste vide

Solution: DÉJÀ APPLIQUÉE - Topics créés
À faire: Redémarrer Consumer pour qu'il voie les topics
```

**Solution immédiate**:
```bash
docker compose restart data-consumer
```

---

### 🔴 PROBLÈME #3: Anciens Scripts Utilisés?
```
Localisation:
- codes/data_logger.py      (ANCIEN, 18 cols) ← À SUPPRIMER
- codes/app.py              (ANCIEN, 18 cols) ← À SUPPRIMER
- codes/data_logger_NEW.py  (BON, 19 cols)    ← À UTILISER
- codes/app_NEW.py          (BON, 19 cols)    ← À UTILISER

Risque: Si RPi exécute data_logger.py (ancien):
- CSV: 18 colonnes ✅
- Kafka: Manque irrigation_status ❌
- PostgreSQL: Insère NULL ❌
- Grafana: Affiche 0 ❌
```

**Solution immédiate**:
```bash
# Sur RPi, vérifier quel script s'exécute:
ps aux | grep data_logger
# Doit afficher: data_logger_NEW.py

# Si c'est l'ancien, arrêter et démarrer le nouveau:
pkill -f "python.*data_logger"
python3 data_logger_NEW.py &
```

---

## État Actuel des Fichiers

| Fichier | Cols | Status | Action |
|---------|------|--------|--------|
| data_logger.py | 18 | ❌ Ancien | Renommer → data_logger_OLD.py |
| data_logger_NEW.py | 19 | ✅ Correct | Renommer → data_logger.py |
| app.py | 18 | ❌ Ancien | Renommer → app_OLD.py |
| app_NEW.py | 19 | ✅ Correct | Renommer → app.py |
| consumer.py | N/A | ✅ OK | Redémarrer container |
| init.sql | N/A | ✅ OK | Aucune action |
| docker-compose.yml | N/A | ⚠️ À améliorer | Ajouter KAFKA_AUTO_CREATE_TOPICS_ENABLE |

---

## État du Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    STATUT DU PIPELINE                        │
└──────────────────────────────────────────────────────────────┘

Capteurs MQTT (LoRa)
    │
    ✅ → MQTT Listener (localhost:1883)
    │
    ├─ CSV Writer ✅
    │  └─ File: data_logger.csv (19 cols) ✅
    │
    ├─ Kafka Producer ❌
    │  └─ Status: kafka_producer = None (kafka-python NOT installed)
    │  └─ Message Sent: 0/100+ today
    │
    └─ Kafka Topic: iot_smart_irrigation
       │
       ├─ Status: CRÉÉ (manuellement)
       ├─ Messages: 0 (en attente du RPi)
       │
       └─ Consumer
          │
          ├─ Status: ACTIF (UP 5 min)
          ├─ Messages Reçus: 0
          │
          └─ PostgreSQL
             │
             ├─ Table: iot_smart_irrigation_raw
             ├─ Rows: 2 (STALE, 40+ min old)
             ├─ Expected: 100+ per day
             │
             └─ Grafana
                ├─ Status: "No data" ❌
                └─ Fix: Attendre données PostgreSQL

Status Global: 🔴 CASSÉ (Kafka Producer broken)
Gravité: CRITIQUE (0% data flow)
```

---

## Dépendances RPi

```bash
# Sur le RPi, packages OBLIGATOIRES:
pip3 list | grep -E "kafka|paho|numpy|joblib|psutil|requests"

# Doit afficher:
confluent-kafka OU kafka-python     ← MANQUANT! 🚨
paho-mqtt                            ← ✅
numpy                                ← ✅
joblib                               ← ✅
psutil                               ← ✅ (optional)
requests                             ← ✅
streamlit                            ← ✅ (for app.py)

# Install manquant:
pip3 install kafka-python
```

---

## Vérifications Rapides

### 1️⃣ Vérifier que data_logger_NEW.py s'exécute
```bash
# Sur RPi:
ps aux | grep python | grep data_logger
# Doit afficher: python3 data_logger_NEW.py
```

### 2️⃣ Vérifier que MQTT messages arrivent
```bash
# Sur RPi:
mosquitto_sub -h localhost -t "irrigation/soil/#" &
# Doit afficher des messages JSON toutes les 5-10 secondes
```

### 3️⃣ Vérifier que Kafka Topics existent
```bash
# Sur Desktop:
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Doit afficher:
# __consumer_offsets
# iot_smart_irrigation ✅
# soil_moisture ✅
```

### 4️⃣ Vérifier que Consumer reçoit messages
```bash
# Sur Desktop:
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic iot_smart_irrigation \
  --max-messages 1 \
  --timeout-ms 5000
# Doit afficher: JSON message OU (null si aucun message)
```

### 5️⃣ Vérifier PostgreSQL
```bash
# Sur Desktop:
docker exec postgres psql -U airflow -d airflow \
  -c "SELECT COUNT(*) as total_rows, MAX(timestamp) as latest FROM iot_smart_irrigation_raw;"
# Doit afficher:
# total_rows | latest
# -----------+----------------------------
#       100+ | 2026-04-14 23:XX:XX (recent)
```

---

## Ordre de Fix (Exécution)

### ✅ DÉJÀ FAIT:
1. Topics Kafka créés
2. Consumer container actif

### ⏳ À FAIRE IMMÉDIATEMENT:

#### Étape 1: Installer kafka-python sur RPi (5 min)
```bash
ssh pi@192.168.100.66
pip3 install kafka-python
# ou: pip3 install confluent-kafka
```

#### Étape 2: Arrêter ancien script + Démarrer le nouveau (2 min)
```bash
ssh pi@192.168.100.66
pkill -f "python.*data_logger"
cd ~/
python3 data_logger_NEW.py &  # OU systemd service
```

#### Étape 3: Redémarrer Consumer (1 min)
```bash
docker compose restart data-consumer
```

#### Étape 4: Vérifier Kafka reçoit messages (2 min)
```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic iot_smart_irrigation \
  --max-messages 3
# Doit afficher: JSON messages
```

#### Étape 5: Vérifier PostgreSQL (1 min)
```bash
docker exec postgres psql -U airflow -d airflow \
  -c "SELECT COUNT(*) FROM iot_smart_irrigation_raw; \
      SELECT * FROM iot_smart_irrigation_raw ORDER BY timestamp DESC LIMIT 1;"
# Doit afficher: >10 rows + recent timestamp
```

#### Étape 6: Vérifier Grafana (1 min)
```
Browser: http://192.168.100.97:3000
Dashboard: Doit afficher des graphes (pas "No data")
```

**Temps Total: 15 minutes**

---

## Symptômes vs Causes

| Symptôme | Cause | Fix |
|----------|-------|-----|
| Grafana "No data" | PostgreSQL vide | Installer kafka-python RPi |
| Consumer 0 messages | Kafka vide | Redémarrer + installer kafka-python |
| CSV local OK, Cloud ❌ | PostgreSQL vide | Installer kafka-python RPi |
| Streamlit timeout | PostgreSQL slow/empty | Installer kafka-python RPi |

---

## Fichiers à Consulter

```
WORKSPACE_AUDIT_REPORT.md       ← RAPPORT COMPLET (ce document)
QUICK_DIAGNOSIS_CHART.md        ← CE FICHIER (résumé rapide)
codes/data_logger_NEW.py        ← À EXÉCUTER SUR RPi
codes/app_NEW.py                ← À DÉPLOYER SUR RPi
projet-dataops-mlops/data_ingestion/consumer.py ← ACTIF
```

---

## Contact / Support

Si les 15 minutes de fix ne résolvent pas l'issue:

1. Vérifier les logs du Consumer:
   ```bash
   docker logs projet-dataops-mlops-data-consumer-1 --tail 100
   ```

2. Vérifier les logs Kafka:
   ```bash
   docker logs projet-dataops-mlops-kafka-1 --tail 50
   ```

3. Vérifier si RPi peut atteindre Kafka:
   ```bash
   ssh pi@192.168.100.66
   python3 -c "from kafka import KafkaProducer; print('OK')"
   ```

---

**Status**: 🔴 BLOQUÉ sur kafka-python  
**Gravité**: CRITIQUE  
**ETA Fix**: 15 minutes  
**Dernière mise à jour**: 2026-04-14 23:45:00
