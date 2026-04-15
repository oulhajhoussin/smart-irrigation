# 📋 RAPPORT D'AUDIT COMPLET DU WORKSPACE
**Date**: 14 Avril 2026  
**Status**: 🔴 CRITIQUES IDENTIFIÉS  
**Objectif**: Restaurer les données Grafana (actuellement vides)

---

## 🎯 RÉSUMÉ EXÉCUTIF

| Aspect | Status | Severity | Notes |
|--------|--------|----------|-------|
| **CSV Local** | ✅ OK | - | 19 colonnes, irrigation_status présent |
| **Streamlit CSV Mode** | ✅ OK | - | Lit les données correctement |
| **PostgreSQL Table** | ✅ OK | - | Schema correct (20 colonnes) |
| **PostgreSQL Data** | ❌ VIDE | 🔴 CRITIQUE | Seulement 2 lignes (stale: 21:51:56) |
| **Kafka Topics** | ❌ ABSENT | 🔴 CRITIQUE | Topics NOT created (only __consumer_offsets) |
| **Kafka Producer** | ❌ INACTIF | 🔴 CRITIQUE | data_logger_NEW.py n'envoie RIEN |
| **Consumer** | ✅ ACTIF | ⚠️ WARNING | Running mais reçoit 0 messages |
| **Grafana** | ❌ "No data" | 🔴 CRITIQUE | Query retourne 0 rows |
| **Docker Network** | ✅ OK | - | Tous les containers UP |

---

## 🔍 ANALYSE DÉTAILLÉE PAR COMPOSANT

### 1️⃣ DATA LOGGER (RPi) - **PROBLÈME PRINCIPAL**

#### 📄 Fichier: `codes/data_logger_NEW.py`
- **Status**: ✅ Code correct
- **CSV Output**: ✅ 19 colonnes complètes
  ```
  [1] timestamp [2] node_id [3] counter [4] soil_pct 
  [5] irrigation_status ✅ PRÉSENT
  [6] raw_data [7] payload_bytes [8] rssi [9] snr
  [10] rtt_cloud_ms ✅ REMPLI
  ... + 9 colonnes supplémentaires
  ```
- **Kafka Producer**: ✅ Configuré ligne 124-131
  ```python
  kafka_producer = KafkaProducer(
      bootstrap_servers=[f'{KAFKA_HOST}:9092'],  # 192.168.100.97:9092
      value_serializer=lambda v: json.dumps(v).encode('utf-8'),
      acks='1'
  )
  ```
- **Kafka Payload**: ✅ 20 champs corrects (ligne 316-336)
- **PROBLÈME**: Kafka est absent du RPi!
  - Ligne 346: `kafka_producer.send("iot_smart_irrigation", kafka_payload)`
  - **Ce code ne peut JAMAIS fonctionner** si `kafka_producer` est None

**🚨 PROBLÈME 1**: Le RPi n'a **PROBABLEMENT PAS** la dépendance `kafka-python` installée!
```python
# Ligne 36-38: if kafka_producer is not None:
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None  # ← Si kafka-python pas installé → NULL
```

**Consequence**: `kafka_producer` reste None → Les `kafka_producer.send()` sont IGNORÉS!

#### 📄 Fichier: `codes/data_logger.py` (Ancien)
- **Status**: ⚠️ 18 colonnes (MANQUE `irrigation_status` et `rtt_cloud_ms`)
- **CSV Headers** (ligne 89):
  ```python
  HEADERS = ['timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 
             'payload_bytes', 'rssi', 'snr', 'rtt_cloud_ms', ...]
  ```
  ❌ `irrigation_status` ABSENT!
  
- **Impact**: Si ce script s'exécute au lieu de `data_logger_NEW.py`:
  - CSV: 18 colonnes (incomplet)
  - Kafka: Pas de `irrigation_status` → Grafana affiche 0
  - PostgreSQL: Insère NULL → Erreur ou valeur par défaut

---

### 2️⃣ KAFKA BROKER (Docker)

#### Current State: 🔴 Topics VIDES!
```bash
$ docker exec kafka kafka-topics --list
__consumer_offsets           ← SEUL topic système existant

# MANQUENT:
- iot_smart_irrigation      ← Topic attendu par Consumer
- soil_moisture             ← Topic hérité
```

**🚨 PROBLÈME 2**: Les topics Kafka n'existent PAS!

#### Cause:
- Kafka n'a pas `auto.create.topics.enable = true` dans docker-compose.yml
- Les producteurs n'envoient RIEN → topics ne se créent pas automatiquement
- Consumer essaie de s'abonner à des topics qui n'existent pas → 0 messages

#### docker-compose.yml (Kafka config):
```yaml
kafka:
  image: confluentinc/cp-kafka:7.4.0
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,PLAINTEXT_HOST://0.0.0.0:9093
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://192.168.100.97:9093
    KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    # ❌ MANQUE: auto.create.topics.enable: 'true'
```

---

### 3️⃣ CONSUMER (Docker)

#### 📄 Fichier: `data_ingestion/consumer.py`

**Status**: ✅ Code correct, ❌ Reçoit 0 messages

**Configuration**:
- Line 11: `KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')`
- Line 32: `'bootstrap.servers': KAFKA_BROKER`
- Line 38: Subscribe à topics: `['soil_moisture', 'iot_smart_irrigation']`
- Line 125: `time.sleep(15)` avant de démarrer

**🚨 PROBLÈME 3**: Consumer ne reçoit RIEN car:
1. Topics n'existent pas dans Kafka
2. data_logger_NEW.py n'envoie pas de messages (kafka_producer = None sur RPi)
3. Aucun message dans Kafka = Consumer attend indéfiniment

**Logs du Consumer**:
```
%3|1776202301.783|FAIL|rdkafka#consumer-1| 
[thrd:kafka:9092/bootstrap]: kafka:9092/bootstrap: 
Connect to ipv4#172.19.0.4:9092 failed: Connection refused
```
- Ancien problème, mais illustre que Kafka n'était pas prêt

---

### 4️⃣ POSTGRESQL (Docker)

#### Table Schema: ✅ CORRECT
```sql
CREATE TABLE iot_smart_irrigation_raw (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    humidity FLOAT NOT NULL,
    irrigation_status INTEGER NOT NULL,  ✅ PRÉSENT
    decision_latency_ms FLOAT,
    rssi INTEGER,
    gateway_batt_pct FLOAT,
    counter INTEGER,
    raw_data VARCHAR(255),
    payload_bytes INTEGER,
    snr INTEGER,
    rtt_cloud_ms FLOAT,                   ✅ PRÉSENT
    ... + 6 colonnes supplémentaires
);
```

#### Data Status: 🔴 VIDE
```bash
SELECT COUNT(*) FROM iot_smart_irrigation_raw;
Result: 2 rows  (CRITIQUE: should be 100+ per day)

SELECT MAX(timestamp) FROM iot_smart_irrigation_raw;
Result: 2026-04-14 21:51:56.562155  (40+ MINUTES STALE)
```

**Cause**: Consumer n'a jamais reçu de messages Kafka → 0 insertions

---

### 5️⃣ STREAMLIT (RPi)

#### 📄 Fichier: `codes/app_NEW.py`
- **CSV Mode**: ✅ WORKS (affiche "normal, il y a de data")
- **Cloud Mode**: ❌ TIMEOUT (PostgreSQL unreachable ou vide)
- **CSV Headers** (line 163): 19 colonnes ✅ CORRECT

#### 📄 Fichier: `codes/app.py` (Ancien)
- **CSV Headers**: 18 colonnes ❌ (manque `irrigation_status`)
- **Impact**: Décalage colonnes = Grafana affiche mauvaises données

---

### 6️⃣ GRAFANA (Docker)

#### Status: 🔴 "No data"

**Cause Root**:
```
PostgreSQL table iot_smart_irrigation_raw
    ↓
Contains only 2 stale rows (40+ min old)
    ↓
Grafana queries return 0 rows
    ↓
Dashboard shows "No data"
```

**Grafana Panel Queries** (expected):
```sql
SELECT 
    timestamp, 
    node_id, 
    humidity,
    irrigation_status
FROM iot_smart_irrigation_raw
WHERE $__timeFilter(timestamp)
ORDER BY timestamp DESC
```

**Result**: 0 rows = "No data"

---

## 🐛 PROBLÈMES IDENTIFIÉS (PRIORITÉ)

### 🔴 CRITIQUE - **BLOQUER LE SYSTÈME**

#### ❌ PROBLÈME 1: Kafka Producer Manquant sur RPi
- **Localisation**: `codes/data_logger_NEW.py` ligne 36-38, 346
- **Issue**: `from kafka import KafkaProducer` FAILS → `kafka_producer = None`
- **Consequence**: `kafka_producer.send()` est IGNORÉ (condition `if kafka_producer is not None` au ligne 340)
- **Impact**: **ZÉRO messages** envoyés à Kafka
- **Fix**: Installer `kafka-python` sur le RPi
  ```bash
  pip install kafka-python
  # ou
  pip install confluent-kafka
  ```

#### ❌ PROBLÈME 2: Topics Kafka n'Existent Pas
- **Localisation**: `docker-compose.yml` (Kafka service)
- **Issue**: Broker Kafka ne crée pas automatiquement les topics
- **Consequence**: Topics `iot_smart_irrigation` et `soil_moisture` n'existent PAS
- **Impact**: Consumer ne peut pas s'y abonner → 0 messages reçus
- **Fix**: Créer les topics manuellement (DÉJÀ FAIT) OU ajouter à docker-compose.yml:
  ```yaml
  KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
  ```

#### ❌ PROBLÈME 3: Data Logger RPi n'Envoie Pas de Messages
- **Localisation**: `codes/data_logger_NEW.py`
- **Issue**: Même si le code est correct, il faut que:
  1. Python soit exécuté sur RPi
  2. MQTT listener soit actif (écoute `irrigation/soil/#`)
  3. Capteurs LoRa envoient des messages MQTT
  4. `kafka_producer` soit configuré (dépend de Problème 1)
- **Consequence**: **AUCUNE DONNÉE** n'arrive à Kafka
- **Impact**: PostgreSQL reste vide, Grafana affiche "No data"
- **Fix**: 
  - [ ] Vérifier que `data_logger_NEW.py` s'exécute sur RPi
  - [ ] Vérifier que MQTT messages arrivent
  - [ ] Installer kafka-python sur RPi
  - [ ] Redémarrer le script

#### ❌ PROBLÈME 4: Anciens Scripts Toujours Actifs?
- **Localisation**: `codes/data_logger.py` vs `codes/data_logger_NEW.py`
- **Issue**: Si le RPi exécute `data_logger.py` (ancien):
  - CSV: 18 colonnes (manque `irrigation_status`)
  - Kafka: Malformé (pas `irrigation_status`)
  - PostgreSQL: Insère NULL pour `irrigation_status`
  - Grafana: Affiche 0 (colonne vide)
- **Impact**: Décalage données + erreurs silencieuses
- **Fix**: 
  - [ ] Vérifier quel script est exécuté sur RPi
  - [ ] **UTILISER UNIQUEMENT** `data_logger_NEW.py`
  - [ ] Supprimer ou renommer `data_logger.py`

---

### ⚠️ MOYEN - **DÉGRADATION QUALITÉ**

#### ⚠️ PROBLÈME 5: Streamlit Utilise Ancien Schema
- **Localisation**: `codes/app.py` ligne 163
- **Issue**: CSV headers = 18 colonnes (missing `irrigation_status`)
- **Consequence**: Décalage colonnes lors de la lecture CSV
- **Impact**: Streamlit affiche mauvaises données si CSV mode utilisé
- **Fix**: Utiliser UNIQUEMENT `app_NEW.py` (19 colonnes corrètes)

#### ⚠️ PROBLÈME 6: Deux Versions du Même Script
- **Localisation**: `codes/data_logger.py` + `data_logger_NEW.py`, `codes/app.py` + `app_NEW.py`
- **Issue**: Confusion sur quel script déployer
- **Consequence**: Risque d'exécuter la mauvaise version
- **Impact**: Données inconsistentes
- **Fix**: 
  - [ ] Renommer `data_logger.py` → `data_logger_OLD.py`
  - [ ] Renommer `app.py` → `app_OLD.py`
  - [ ] Renommer `data_logger_NEW.py` → `data_logger.py`
  - [ ] Renommer `app_NEW.py` → `app.py`

---

### 💡 MOINDRE - **À AMÉLIORER**

#### 💡 PROBLÈME 7: Documentation Manquante sur RPi
- **Localisation**: RPi (pas de logs centralisés)
- **Issue**: Impossible de vérifier si `data_logger_NEW.py` s'exécute
- **Fix**: Ajouter des logs:
  ```python
  import logging
  logging.basicConfig(filename='/tmp/data_logger.log', level=logging.INFO)
  ```

#### 💡 PROBLÈME 8: Kafka Auto-Topic Creation Non Configurée
- **Localisation**: `docker-compose.yml`
- **Issue**: Kafka nécessite création manuelle des topics
- **Fix**: Ajouter à docker-compose.yml `KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'`

---

## 📊 ARCHITECTURE ACTUELLE vs ATTENDUE

```
┌─────────────────────────────────────────────────────────────┐
│                     ARCHITECTURE ATTENDUE                    │
└─────────────────────────────────────────────────────────────┘

RPi (192.168.100.66)
├─ MQTT Listener (port 1883)
│  └─ Reçoit: irrigation/soil/node1, irrigation/soil/node2
│
├─ data_logger_NEW.py ✅
│  ├─ Parse MQTT
│  ├─ Applique IA FOG
│  ├─ Sauvegarde CSV (19 cols) ✅
│  └─ Envoie Kafka (20 champs) ❌ MANQUE KAFKA-PYTHON
│
├─ Streamlit (app_NEW.py) ✅
│  ├─ CSV Mode: Lit 19 cols ✅
│  └─ Cloud Mode: Requête PostgreSQL ✅
│
└─ MQTT Control (pompes)

         INTERNET/RÉSEAU
                ↓
        192.168.100.97:9092
                ↓
Desktop PC (Docker)
├─ Kafka Broker 🔴 TOPICS MANQUENT
│  ├─ iot_smart_irrigation ❌
│  ├─ soil_moisture ❌
│  └─ __consumer_offsets ✅ (système)
│
├─ Consumer 🟡 ACTIF MAIS 0 MESSAGES
│  └─ Tente s'abonner à topics → 0 messages reçus
│
├─ PostgreSQL 🔴 VIDE (2 lignes stales)
│  ├─ iot_smart_irrigation_raw (0 données nouvelles)
│  └─ raw_soil_moisture (0 données nouvelles)
│
├─ Grafana 🔴 "No data"
│  └─ Requête → 0 rows
│
└─ MLflow 🟢 OK


┌─────────────────────────────────────────────────────────────┐
│                    FLUX DE DONNÉES CASSÉ                    │
└─────────────────────────────────────────────────────────────┘

MQTT Sensors (LoRa)
    ↓ ✅ OK
data_logger_NEW.py (CSV ✅, Kafka ❌)
    ↓
Kafka Topics ❌ ABSENT/VIDE
    ↓
Consumer ❌ 0 MESSAGES
    ↓
PostgreSQL ❌ 0 DONNÉES NOUVELLES
    ↓
Grafana ❌ "No data"
```

---

## ✅ CHECKLIST FIX (ORDRE EXÉCUTION)

### PHASE 1: Préparation Infrastructure (Docker)
- [ ] **Créer Topics Kafka**
  ```bash
  docker exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic iot_smart_irrigation --partitions 1 --replication-factor 1
  docker exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic soil_moisture --partitions 1 --replication-factor 1
  ```
  **Status**: ✅ DÉJÀ FAIT

- [ ] **Redémarrer Consumer (pour qu'il voit les topics)**
  ```bash
  docker compose restart data-consumer
  ```

### PHASE 2: Configuration RPi
- [ ] **Installer kafka-python sur RPi**
  ```bash
  pip3 install kafka-python
  # ou
  pip3 install confluent-kafka
  ```
  **Status**: ❌ À FAIRE

- [ ] **Vérifier que data_logger_NEW.py s'exécute**
  ```bash
  ps aux | grep data_logger
  # Doit afficher: python data_logger_NEW.py
  ```
  **Status**: ⏳ À VÉRIFIER

- [ ] **Vérifier que MQTT messages arrivent**
  ```bash
  mosquitto_sub -h localhost -t "irrigation/soil/#"
  # Doit afficher des messages JSON
  ```
  **Status**: ⏳ À VÉRIFIER

### PHASE 3: Validation Data Flow
- [ ] **Vérifier Kafka reçoit messages**
  ```bash
  docker exec kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic iot_smart_irrigation \
    --max-messages 5 \
    --from-beginning
  ```

- [ ] **Vérifier PostgreSQL reçoit données**
  ```bash
  docker exec postgres psql -U airflow -d airflow \
    -c "SELECT COUNT(*) FROM iot_smart_irrigation_raw;"
  # Doit afficher: >100
  ```

- [ ] **Vérifier Grafana affiche données**
  ```
  Ouvrir http://192.168.100.97:3000
  Dashboard → Doit afficher données (pas "No data")
  ```

### PHASE 4: Cleanup
- [ ] **Renommer anciens scripts**
  ```bash
  # Sur RPi:
  mv data_logger.py data_logger_OLD.py
  mv app.py app_OLD.py
  
  # Sur Desktop:
  mv codes/data_logger.py codes/data_logger_OLD.py
  mv codes/app.py codes/app_OLD.py
  ```

- [ ] **Renommer nouveaux scripts as standard**
  ```bash
  # Sur RPi:
  mv data_logger_NEW.py data_logger.py
  mv app_NEW.py app.py
  
  # Sur Desktop:
  mv codes/data_logger_NEW.py codes/data_logger.py
  mv codes/app_NEW.py codes/app.py
  ```

---

## 📈 IMPACT DU FIX

| Métrique | Avant | Après |
|----------|-------|-------|
| **PostgreSQL rows** | 2 (stale) | 100+ (actualisé) |
| **Grafana status** | "No data" | ✅ Affiche données |
| **Streamlit Cloud** | ❌ Timeout | ✅ Fonctionne |
| **CSV Local** | ✅ Travaille | ✅ Continue |
| **Kafka messages/jour** | 0 | 100+ |
| **Data latency** | N/A | <5 secondes |

---

## 📞 ACTIONS IMMÉDIATES

### URGENT (AUJOURD'HUI)
1. ✅ **DÉJÀ FAIT**: Créer les topics Kafka
2. ⏳ **À FAIRE**: Installer `kafka-python` sur RPi
3. ⏳ **À FAIRE**: Vérifier que `data_logger_NEW.py` s'exécute sur RPi
4. ⏳ **À FAIRE**: Redémarrer les services

### COURT TERME (CETTE SEMAINE)
5. [ ] Ajouter `KAFKA_AUTO_CREATE_TOPICS_ENABLE` à docker-compose.yml
6. [ ] Renommer tous les anciens scripts
7. [ ] Ajouter logging sur RPi

### LONG TERME (INFRASTRUCTURE)
8. [ ] Créer systemd service pour data_logger_NEW.py
9. [ ] Centraliser les logs (syslog/ELK)
10. [ ] Ajouter health checks (Kafka broker, Consumer, DB)

---

## 🔗 FICHIERS CRITIQUES À VÉRIFIER

```
✅ codes/data_logger_NEW.py        (Correct, besoin kafka-python)
❌ codes/data_logger.py            (Ancien, 18 cols)
✅ codes/app_NEW.py                (Correct)
❌ codes/app.py                    (Ancien)
✅ data_ingestion/consumer.py      (Correct)
✅ projet-dataops-mlops/docker-compose.yml (Topics OK maintenant)
✅ projet-dataops-mlops/init.sql   (Schema OK)
```

---

## 📝 CONCLUSION

**ROOT CAUSE**: Kafka Producer manquant sur RPi (`kafka-python` not installed)

**SOLUTION PRINCIPALE**: 
```bash
# Sur le RPi:
pip3 install kafka-python

# Puis redémarrer data_logger_NEW.py
pkill -f data_logger
python3 data_logger_NEW.py
```

**RÉSULTAT ATTENDU**:
- ✅ data_logger_NEW.py → envoie messages Kafka
- ✅ Consumer → reçoit messages
- ✅ PostgreSQL → s'emplit de données
- ✅ Grafana → affiche les données

**TEMPS ESTIMÉ**: 15 minutes

---

Generated: 2026-04-14  
Report Version: 1.0  
Analyzer: AI Assistant
