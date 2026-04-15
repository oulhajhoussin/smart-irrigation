# ⚡ DEPLOYMENT FIX - ACTION PLAN (15 min)

**Objectif**: Restaurer le flux données Grafana (actuellement: "No data")

**Problème Root**: `kafka-python` NOT INSTALLED sur RPi → data_logger_NEW.py n'envoie rien

---

## 🎯 PHASE 1: RPi Setup (5 minutes)

### Step 1.1: SSH to RPi
```bash
ssh pi@192.168.100.66
# Password: (votre password RPi)
```

### Step 1.2: Install kafka-python
```bash
# Vérifier d'abord si installé:
python3 -c "from kafka import KafkaProducer; print('kafka-python already installed')"

# Si erreur ImportError, installer:
pip3 install kafka-python

# OU alternative (confluent):
pip3 install confluent-kafka

# Vérifier installation:
python3 -c "from kafka import KafkaProducer; print('✅ kafka-python installed')"
```

### Step 1.3: Stop old data logger (if running)
```bash
# Vérifier quel script s'exécute:
ps aux | grep "[d]ata_logger"

# Si vous voyez data_logger.py ou data_logger_NEW.py:
pkill -f "data_logger"

# Vérifier qu'il s'est arrêté:
ps aux | grep "[d]ata_logger"
# Doit retourner VIDE
```

### Step 1.4: Start data_logger_NEW.py
```bash
cd ~/  # ou le répertoire où vous avez data_logger_NEW.py

# Vérifier que le fichier existe:
ls -la data_logger_NEW.py

# Lancer le script:
python3 data_logger_NEW.py &

# Vérifier qu'il a démarré:
ps aux | grep "[d]ata_logger"
# Doit afficher: python3 data_logger_NEW.py
```

### Step 1.5: Verify MQTT messages (optional but recommended)
```bash
# Dans un autre terminal SSH (ou Ctrl+Z to background):
mosquitto_sub -h localhost -t "irrigation/soil/#" | head -5

# Doit afficher JSON messages comme:
# {
#   "raw": "...",
#   "rssi": -85,
#   "snr": 10,
#   ...
# }

# Si rien n'apparaît après 30 secondes:
# → Capteurs LoRa may not be sending → Check gateway
```

---

## 🎯 PHASE 2: Docker Restart (3 minutes)

### Step 2.1: Restart Consumer container
```bash
# Sur votre Desktop (pas le RPi):
cd c:\Users\GODFATHER\Desktop\dataset\projet-dataops-mlops

docker compose restart data-consumer

# Vérifier qu'il a redémarré:
docker ps | findstr consumer
# Doit afficher: Up (new time)
```

### Step 2.2: Check Consumer logs (optional)
```bash
# Attendre 5 secondes pour que Consumer soit prêt
Start-Sleep -Seconds 5

docker logs projet-dataops-mlops-data-consumer-1 --tail 20

# Doit afficher (après ~20 secondes):
# [iot_smart_irrigation] Received: {"timestamp": ..., "node_id": ...}
# Inserts into DB...
```

---

## 🎯 PHASE 3: Verification (5 minutes)

### Step 3.1: Verify Kafka receives messages
```bash
docker exec projet-dataops-mlops-kafka-1 kafka-console-consumer `
  --bootstrap-server localhost:9092 `
  --topic iot_smart_irrigation `
  --max-messages 3 `
  --timeout-ms 10000

# Doit afficher (après ~30 sec):
# {"timestamp": "2026-04-14T23:XX:XX...", "node_id": "node1", ...}
# {"timestamp": "2026-04-14T23:XX:XX...", "node_id": "node2", ...}
# ...

# Si timeout/null:
# → RPi toujours pas envoyer de messages
# → Vérifier kafka-python install + data_logger_NEW.py running
```

### Step 3.2: Verify PostgreSQL has new data
```bash
docker exec projet-dataops-mlops-postgres-1 psql -U airflow -d airflow `
  -c "SELECT COUNT(*) as total_rows, MAX(timestamp) as latest FROM iot_smart_irrigation_raw;"

# AVANT FIX:
#  total_rows |           latest           
# -----------+----------------------------
#           2 | 2026-04-14 21:51:56.562155

# APRÈS FIX (attendu après 2-3 min):
#  total_rows |           latest           
# -----------+----------------------------
#          15 | 2026-04-14 23:45:30.123456

# Si toujours 2 rows / old timestamp:
# → Messages Kafka pas reçus par Consumer
# → Vérifier Step 3.1
```

### Step 3.3: Verify Grafana displays data
```
1. Browser: http://192.168.100.97:3000
2. Login: admin / admin
3. Dashboard: Smart Irrigation
4. Panels: Doit afficher des courbes/graphes (pas "No data")

AVANT FIX:
- Tous les panneaux: "No data"
- Grafana logs: Query returned 0 rows

APRÈS FIX (attendu après 5 min):
- Panneaux: Affichent irrigation_status, humidity, etc.
- Logs: Query returned 10+ rows
```

### Step 3.4: Verify Streamlit Cloud mode works
```bash
# Lancez Streamlit:
streamlit run app_NEW.py

# Ou accédez si déployé:
http://192.168.100.66:8501 (ou votre URL)

AVANT FIX:
- Streamlit Cloud (SQL): "PostgreSQL Indisponible" (timeout)
- Streamlit CSV: ✅ Fonctionne (fallback)

APRÈS FIX:
- Streamlit Cloud (SQL): ✅ Affiche données
- Streamlit CSV: ✅ Continue fonctionner
```

---

## 🚨 Troubleshooting

### If PostgreSQL still shows 2 rows after 10 minutes:

#### Check 1: RPi really sending Kafka messages?
```bash
# Vérifier que data_logger_NEW.py s'exécute:
ssh pi@192.168.100.66
ps aux | grep data_logger

# Doit afficher: python3 data_logger_NEW.py

# Si pas affiché:
cd ~/
python3 data_logger_NEW.py &
```

#### Check 2: Kafka reçoit messages?
```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic iot_smart_irrigation \
  --max-messages 1 \
  --timeout-ms 15000

# Si null:
# 1. Vérifier Step 1.2 (kafka-python installed on RPi)
# 2. Vérifier MQTT messages arrivent (Step 1.5)
# 3. Vérifier RPi peut atteindre Kafka:
#    ssh pi@192.168.100.66
#    python3 -c "from kafka import KafkaProducer; \
#                KafkaProducer(bootstrap_servers=['192.168.100.97:9092']); \
#                print('✅ Connected')"
```

#### Check 3: Consumer has errors?
```bash
docker logs projet-dataops-mlops-data-consumer-1 --tail 50

# Chercher les erreurs comme:
# - "Connection refused" → Kafka pas prêt
# - "INSERT" errors → Schema mismatch
# - "json decode error" → Payload format wrong
```

#### Check 4: PostgreSQL is running?
```bash
docker exec postgres pg_isready
# Doit retourner: accepting connections

# Vérifier la table existe:
docker exec postgres psql -U airflow -d airflow \
  -c "SELECT column_name FROM information_schema.columns \
      WHERE table_name = 'iot_smart_irrigation_raw';"

# Doit lister 20 colonnes
```

---

## 📊 Expected Timeline

| Time | Status | What's Happening |
|------|--------|------------------|
| T+0 min | Start | Install kafka-python |
| T+2 min | In Progress | Restart data_logger_NEW.py |
| T+5 min | Sending | RPi sends 1st messages to Kafka |
| T+10 min | Consuming | Consumer receives messages, inserts to PostgreSQL |
| T+12 min | Visible | Grafana refreshes, shows data |
| T+15 min | ✅ DONE | All systems operational |

---

## 🎯 Quick Reference Commands

```bash
# ===== RPi COMMANDS =====
ssh pi@192.168.100.66
pip3 install kafka-python
ps aux | grep data_logger
pkill -f data_logger
python3 data_logger_NEW.py &
mosquitto_sub -h localhost -t "irrigation/soil/#"

# ===== DOCKER COMMANDS =====
docker compose restart data-consumer
docker logs projet-dataops-mlops-data-consumer-1 --tail 50
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
docker exec postgres psql -U airflow -d airflow -c "SELECT COUNT(*) FROM iot_smart_irrigation_raw;"

# ===== VERIFY =====
# Check Kafka messages:
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic iot_smart_irrigation --max-messages 1 --timeout-ms 10000

# Check PostgreSQL:
docker exec postgres psql -U airflow -d airflow -c "SELECT COUNT(*) as total_rows, MAX(timestamp) as latest FROM iot_smart_irrigation_raw;"

# Check Grafana:
# Browser: http://192.168.100.97:3000 → Dashboard → Vérifier data
```

---

## ✅ SUCCESS INDICATORS

- [ ] PostgreSQL COUNT(*) = 10+ (was 2)
- [ ] PostgreSQL MAX(timestamp) = recent (was 40+ min old)
- [ ] Kafka console consumer shows JSON messages
- [ ] Consumer logs show "Received: {...}" and "INSERT INTO"
- [ ] Grafana dashboard shows data (not "No data")
- [ ] Streamlit Cloud mode works (not timeout)

---

## 🔄 OPTIONAL CLEANUP

Once everything is working, you can rename files to avoid confusion:

```bash
# On RPi:
mv data_logger.py data_logger_OLD.py
mv app.py app_OLD.py
# (assuming you've renamed data_logger_NEW.py → data_logger.py already)

# On Desktop:
cd codes/
mv data_logger.py data_logger_OLD.py
mv app.py app_OLD.py
```

---

## 📞 If Still Not Working

Post this in your logs:

1. Output of: `docker logs projet-dataops-mlops-data-consumer-1 --tail 100`
2. Output of: `docker logs projet-dataops-mlops-kafka-1 --tail 50`
3. Output of: `docker exec postgres psql -U airflow -d airflow -c "SELECT * FROM iot_smart_irrigation_raw ORDER BY timestamp DESC LIMIT 3;"`
4. Output of: `ssh pi@192.168.100.66 'ps aux | grep -i python'`
5. Output of: `ssh pi@192.168.100.66 'python3 -c "from kafka import KafkaProducer; print(KafkaProducer(bootstrap_servers=[\"192.168.100.97:9092\"]))'`

---

**Status**: Ready to Deploy  
**Estimated Time**: 15 minutes  
**Difficulty**: Easy (just install 1 package + restart 2 scripts)  
**Last Updated**: 2026-04-14 23:45:00
