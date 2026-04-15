# 🔍 GRAFANA DATA PIPELINE DIAGNOSIS

**Date** : 14/04/2026  
**Problème** : Grafana affiche "No data" après fixes data_logger.py  
**Contexte** : Streamlit fonctionne bien (Mode Cloud + Secours)

---

## 🎯 DIAGNOSTIC

### Symptômes
```
✅ Streamlit : Données visibles (Cloud + CSV)
❌ Grafana : Tous les panneaux affichent "No data"
```

### Chaîne de données
```
IoT Sensors
  ↓
TTGO Gateway + Arduino
  ↓
data_logger.py (MQTT → Kafka → PostgreSQL)
  ↓
PostgreSQL (iot_smart_irrigation_raw table)
  ↓
Grafana (requête SQL sur PostgreSQL)
  ✅ Table existe
  ✅ PostgreSQL running
  ❌ Grafana ne voit pas les données
```

---

## 🔴 CAUSES POSSIBLES

### Cause #1 : Table PostgreSQL pas mise à jour
**Symptôme** : Grafana a une ancienne requête SQL qui ne trouve rien

**Problème potentiel** :
- Avant : data_logger.py envoyait via Kafka → PostgreSQL Consumer
- Maintenant : Vous avez modifié data_logger.py (timestamps, champs)
- **PostgreSQL n'a peut-être pas reçu les nouvelles données**

**Vérification** :
```bash
# Sur Docker
docker exec -it <postgres_container> psql -U airflow -d airflow -c "
SELECT COUNT(*) as total_rows, 
       MAX(timestamp) as last_update 
FROM iot_smart_irrigation_raw;
"

# Expected:
# total_rows | last_update
# -----------+-----------
# > 0        | 2026-04-14...
```

---

### Cause #2 : Kafka n'envoie pas les données à PostgreSQL
**Symptôme** : data_logger.py envoie à Kafka, mais PostgreSQL Consumer ne lit pas

**Problème potentiel** :
- Kafka peut être en retard
- Consumer peut être arrêté
- Topic Kafka peut être vide

**Vérification** :
```bash
# Vérifier Kafka
docker exec -it <kafka_container> kafka-console-consumer.sh \
  --bootstrap-servers localhost:9092 \
  --topic irrigation-data \
  --from-beginning \
  --max-messages 5

# Expected: JSON messages avec données IoT
```

---

### Cause #3 : Grafana requête SQL incorrecte
**Symptôme** : Table existe mais Grafana ne la trouve pas

**Problème potentiel** :
- Grafana pointe sur mauvaise table
- Syntaxe SQL incorrecte
- DataSource PostgreSQL pas connectée

**Vérification** :
```bash
# Tester la requête Grafana
docker exec -it <postgres_container> psql -U airflow -d airflow -c "
SELECT * FROM iot_smart_irrigation_raw LIMIT 5;
"

# Expected: 5 lignes avec données
```

---

### Cause #4 : PostgreSQL Consumer arrêté/defunct
**Symptôme** : Kafka tourne mais Consumer n'écoute pas

**Problème potentiel** :
- Consumer Python arrêté
- Consumer en erreur
- Pas de consumer du tout

**Vérification** :
```bash
# Vérifier les containers Docker
docker compose ps

# Expected: Tous les services UP
# consumer    | UP
# postgres    | UP
# kafka       | UP
```

---

## 🔧 ÉTAPES DE DIAGNOSTIC

### Étape 1 : Vérifier PostgreSQL contient des données
```bash
ssh pi@192.168.100.66

# Depuis le Pi, connecter à PostgreSQL (Docker)
psql -h 192.168.100.97 -U airflow -d airflow -c "
SELECT COUNT(*) as row_count, 
       MAX(timestamp) as latest_update,
       COUNT(DISTINCT node_id) as unique_nodes
FROM iot_smart_irrigation_raw;
"

# Résultats attendus:
# row_count | latest_update      | unique_nodes
# -----------+--------------------+-----------
# 1000+     | 2026-04-14 HH:MM:SS| 2 (node1, node2)
```

### Étape 2 : Vérifier Kafka a les messages
```bash
# Sur PC Docker
docker exec kafka kafka-console-consumer.sh \
  --bootstrap-servers localhost:9092 \
  --topic irrigation-data \
  --max-messages 3 \
  --from-beginning \
  --timeout-ms 10000

# Expected output: JSON messages comme :
# {"timestamp":"2026-04-14T17:19:56","node_id":"node1","soil_pct":15.0,...}
```

### Étape 3 : Vérifier Consumer s'exécute
```bash
# Vérifier Docker Compose
docker compose ps | grep consumer

# Expected: consumer service UP

# Si pas visible, il peut être dans un autre compose
docker ps | grep -i consumer
```

### Étape 4 : Vérifier Grafana DataSource
```
1. Ouvrir Grafana : http://192.168.100.97:3000
2. Aller à : Configuration → Data Sources
3. Chercher : PostgreSQL
4. Vérifier :
   - Host: localhost (ou 127.0.0.1)
   - Port: 5432
   - Database: airflow
   - User: airflow
   - Status: ✅ Green (Connected)

Si rouge → Corriger les paramètres
```

### Étape 5 : Tester requête Grafana manuellement
```bash
# Requête qu'utilise Grafana
docker exec -it <postgres_container> psql -U airflow -d airflow -c "
SELECT 
  timestamp,
  node_id,
  soil_pct as humidity,
  raw_data,
  decision_latency_ms
FROM iot_smart_irrigation_raw
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 100;
"

# Si aucune ligne → Table vide
# Si lignes visibles → Grafana a un problème
```

---

## 🚨 PROBLÈME PROBABLE

Avec vos changements data_logger.py, **les NEW données** n'arrivent peut-être pas à PostgreSQL car :

1. **Kafka n'a pas reçu les new format** 
   - Ancien format : `time.time()` 
   - New format : `datetime.now().isoformat()`
   - Kafka/Consumer peut rejeter le nouveau format

2. **PostgreSQL INSERT échoue silencieusement**
   - Consumer essaie d'insérer
   - Timestamps différents → erreur type
   - Erreur silencieuse → pas de nouvelles données

3. **Consumer pas relancé après changement**
   - Consumer vieux tournait avec old format
   - Vous changez le format
   - Consumer vieux continue avec old format
   - Mélange de formats → erreurs d'insertion

---

## ✅ SOLUTIONS RAPIDES

### Solution #1 : Relancer Consumer
```bash
# Sur Docker
docker compose restart <consumer_service>

# Ou redémarrer tout
docker compose down -v
docker compose up -d
```

**Effet** : Consumer relit Kafka depuis le début avec nouveau code

### Solution #2 : Nettoyer ancien Kafka
```bash
# Supprimer les topics Kafka (⚠️ efface les messages)
docker exec kafka kafka-topics.sh \
  --bootstrap-servers localhost:9092 \
  --delete \
  --topic irrigation-data

# Recreate topic
docker exec kafka kafka-topics.sh \
  --bootstrap-servers localhost:9092 \
  --create \
  --topic irrigation-data \
  --partitions 1 \
  --replication-factor 1
```

**Effet** : Kafka commence frais, pas de vieux messages problématiques

### Solution #3 : Vérifier Consumer logs
```bash
# Voir les logs du consumer
docker compose logs consumer --tail=50

# Chercher des erreurs comme :
# ERROR : json.JSONDecodeError
# ERROR : psycopg2.Error
# ERROR : Unexpected format
```

**Effet** : Identifier l'erreur exacte

---

## 🔧 PLAN D'ACTION

### Étape 1 : Diagnostic (2 min)
```bash
# Vérifier PostgreSQL a des données
psql -h 192.168.100.97 -U airflow -d airflow -c "
SELECT COUNT(*) FROM iot_smart_irrigation_raw;
"

# Si > 0 : Données existent
# Si 0 : Table vide → Consumer pas envoyé
```

### Étape 2 : Si table vide
```bash
# Redémarrer tous les services
docker compose down -v
docker compose up -d

# Attendre 2 minutes que Kafka envoie à PostgreSQL
sleep 120

# Vérifier à nouveau
psql -h 192.168.100.97 -U airflow -d airflow -c "
SELECT COUNT(*) FROM iot_smart_irrigation_raw;
"

# Doit afficher : 100+ lignes
```

### Étape 3 : Vérifier Grafana
```
1. Rafraîchir Grafana : F5
2. Attendre 10 secondes
3. Vérifier panneaux : 
   ✅ "Humidity + Decision IA" → Graphe visible
   ✅ "Decision IA - node1/2" → Données visibles
   ✅ "Latence Moyenne" → Graphe affiché
```

### Étape 4 : Si toujours "No data"
```bash
# Redémarrer data_logger.py sur Pi
ssh pi@192.168.100.66
pkill -f "python.*data_logger.py"
python3 /home/pi/data_logger.py &

# Attendre 30 secondes que les données arrivent
sleep 30

# Vérifier Kafka
docker exec kafka kafka-console-consumer.sh \
  --bootstrap-servers localhost:9092 \
  --topic irrigation-data \
  --max-messages 3

# Attendre 60 secondes que PostgreSQL reçoive
sleep 60

# Vérifier PostgreSQL
psql -h 192.168.100.97 -U airflow -d airflow -c "
SELECT COUNT(*) FROM iot_smart_irrigation_raw;
"

# Doit augmenter
```

---

## 📋 CHECKLIST

- [ ] PostgreSQL contient des données (COUNT > 0)
- [ ] Kafka reçoit les messages (console-consumer affiche JSON)
- [ ] Consumer s'exécute (docker compose ps)
- [ ] Grafana DataSource connectée ✅
- [ ] Grafana panneaux affichent des données
- [ ] Timestamps dans PostgreSQL sont au format ISO ✅

---

**Status** : 🔴 ENQUÊTE EN COURS

**Prochaine étape** : Exécuter les diagnostics ci-dessus et reporter les résultats
