# ✅ INTERACTIVE AUDIT CHECKLIST

**Status**: Ready to Execute  
**Last Updated**: 2026-04-14 23:55:00  
**Your Task**: Work through this checklist step by step

---

## PHASE 0: PRE-AUDIT (What you should know)

- [ ] I have SSH access to RPi (192.168.100.66)
- [ ] I can run Docker commands on Desktop
- [ ] I have access to Grafana dashboard (192.168.100.97:3000)
- [ ] I understand the problem: Grafana shows "No data"

**If you unchecked any**: Read VISUAL_SUMMARY.md before continuing

---

## PHASE 1: DIAGNOSIS (Confirm the issues)

### 1.1: Verify PostgreSQL is empty
```bash
docker exec projet-dataops-mlops-postgres-1 psql -U airflow -d airflow \
  -c "SELECT COUNT(*) as rows, MAX(timestamp) as latest FROM iot_smart_irrigation_raw;"
```

- [ ] I ran the command above
- [ ] Result shows: 2 rows (or fewer) with old timestamp
- [ ] Confirmed: PostgreSQL IS empty

**Expected Output**:
```
 rows |           latest           
------+----------------------------
    2 | 2026-04-14 21:51:56.562155
```

**If different**: Stop here and read WORKSPACE_AUDIT_REPORT.md

---

### 1.2: Verify Kafka topics exist
```bash
docker exec projet-dataops-mlops-kafka-1 kafka-topics --list --bootstrap-server localhost:9092
```

- [ ] I ran the command above
- [ ] Result shows: `iot_smart_irrigation` and `soil_moisture`
- [ ] Confirmed: Topics were created (by previous agent)

**Expected Output**:
```
__consumer_offsets
iot_smart_irrigation
soil_moisture
```

**If missing topics**: Run these:
```bash
docker exec kafka kafka-topics --create --bootstrap-server localhost:9092 --topic iot_smart_irrigation --partitions 1 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --bootstrap-server localhost:9092 --topic soil_moisture --partitions 1 --replication-factor 1 --if-not-exists
```

---

### 1.3: Verify Consumer is running
```bash
docker ps | findstr consumer
```

- [ ] I ran the command above
- [ ] Result shows: `projet-dataops-mlops-data-consumer-1` with status `UP`
- [ ] Confirmed: Consumer is active

**Expected Output**:
```
CONTAINER ID   IMAGE   COMMAND            STATUS
...            ...     python consumer.py Up X minutes
```

**If not running**: `docker compose up -d data-consumer`

---

### 1.4: Verify Kafka has NO messages (yet)
```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic iot_smart_irrigation \
  --max-messages 1 \
  --timeout-ms 3000
```

- [ ] I ran the command above
- [ ] Result shows: (null) or timeout
- [ ] Confirmed: Kafka is empty (expected before RPi sends data)

---

## PHASE 2: ROOT CAUSE CONFIRMATION (Verify the fix target)

### 2.1: Check if kafka-python is installed on RPi
```bash
ssh pi@192.168.100.66 "python3 -c 'from kafka import KafkaProducer; print(\"✅ kafka-python installed\")"
```

- [ ] I ran the command above
- [ ] Result shows: Error (ImportError or ModuleNotFoundError)
- [ ] Confirmed: kafka-python is NOT installed ← **THIS IS THE PROBLEM**

**Expected Output** (broken):
```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'kafka'
```

**OR (success, means already fixed)**:
```
✅ kafka-python installed
```

---

### 2.2: Verify data_logger_NEW.py is NOT running (or running wrong version)
```bash
ssh pi@192.168.100.66 "ps aux | grep '[d]ata_logger'"
```

- [ ] I ran the command above
- [ ] Result shows: Nothing (not running) OR shows old script
- [ ] Confirmed: Need to start correct version

**Expected Output** (not running):
```
(empty)
```

**OR (running old version - also bad)**:
```
... python3 data_logger.py ...  ← Wrong! Should be data_logger_NEW.py
```

---

## PHASE 3: APPLY THE FIX (Now fix it!)

### 3.1: Install kafka-python on RPi
```bash
ssh pi@192.168.100.66 "pip3 install kafka-python"
```

- [ ] I ran the install command
- [ ] Installation completed without errors
- [ ] No "ERROR: Could not find a version" messages

**Time**: 2 minutes  
**Success Indicator**: Command completes and shows "Successfully installed"

---

### 3.2: Verify installation successful
```bash
ssh pi@192.168.100.66 "python3 -c 'from kafka import KafkaProducer; print(\"✅ SUCCESS: kafka-python ready\")'"
```

- [ ] I ran the verify command
- [ ] Result shows: `✅ SUCCESS: kafka-python ready`
- [ ] If not: Retry step 3.1

---

### 3.3: Stop any running data_logger process
```bash
ssh pi@192.168.100.66 "pkill -f 'python.*data_logger'; sleep 2; ps aux | grep '[d]ata_logger'"
```

- [ ] I ran the stop command
- [ ] Result shows: (empty - process stopped)
- [ ] If still running: Run again, then check with `ps aux`

---

### 3.4: Start data_logger_NEW.py
```bash
ssh pi@192.168.100.66 "cd ~/ && python3 data_logger_NEW.py &"
```

- [ ] I ran the start command
- [ ] Command returned (not hanging)

**Time**: 1 minute  
**Next verification in step 4.1**

---

### 3.5: Restart Consumer to ensure it sees topics
```bash
docker compose restart data-consumer
```

- [ ] I ran the restart command
- [ ] Command completed
- [ ] Wait 10 seconds for container to be fully ready

**Time**: 1 minute  
**Status**: Container should show "Up X seconds"

---

## PHASE 4: VERIFICATION (Did it work?)

### 4.1: Verify data_logger_NEW.py is running on RPi
```bash
ssh pi@192.168.100.66 "ps aux | grep '[d]ata_logger'"
```

- [ ] I ran the check
- [ ] Result shows: `python3 data_logger_NEW.py`
- [ ] Confirmed: Correct script is running

**Expected Output**:
```
pi       12345  0.5  2.1 ... python3 data_logger_NEW.py
```

**If missing**: Run 3.4 again

---

### 4.2: Verify Kafka receives messages (wait 20 seconds first)
```bash
Start-Sleep -Seconds 20

docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic iot_smart_irrigation \
  --max-messages 3 \
  --timeout-ms 15000
```

- [ ] I ran the command above
- [ ] Result shows: JSON messages (NOT null/timeout)
- [ ] Confirmed: RPi is sending to Kafka ✅

**Expected Output**:
```json
{
  "timestamp": "2026-04-14T23:55:12...",
  "node_id": "node1",
  "humidity": 45.5,
  "irrigation_status": 1,
  ...
}
{
  "timestamp": "2026-04-14T23:55:22...",
  "node_id": "node2",
  ...
}
```

**If timeout/null**: 
- Check 4.1 (is script running?)
- Check if MQTT is sending messages: `mosquitto_sub -h localhost -t "irrigation/soil/#"` on RPi
- Wait more, Kafka can be slow to show messages

---

### 4.3: Verify Consumer receives and inserts data
```bash
Start-Sleep -Seconds 10

docker logs projet-dataops-mlops-data-consumer-1 --tail 30
```

- [ ] I ran the command above
- [ ] Result shows: `[iot_smart_irrigation] Received: {...]` messages
- [ ] Result shows: `INSERT INTO` statements
- [ ] Confirmed: Consumer is processing ✅

**Expected Output**:
```
[iot_smart_irrigation] Received: {"timestamp": "2026-04-14T23:55:12...", "node_id": "node1", ...}
[iot_smart_irrigation] Received: {"timestamp": "2026-04-14T23:55:22...", "node_id": "node2", ...}
```

**If no messages**:
- Check 4.2 (is Kafka receiving messages?)
- Consumer may take 30+ sec to show logs
- Try again with `--tail 50`

---

### 4.4: Verify PostgreSQL has NEW data
```bash
docker exec projet-dataops-mlops-postgres-1 psql -U airflow -d airflow \
  -c "SELECT COUNT(*) as total_rows, MAX(timestamp) as latest FROM iot_smart_irrigation_raw; \
      SELECT * FROM iot_smart_irrigation_raw ORDER BY timestamp DESC LIMIT 3;"
```

- [ ] I ran the command above
- [ ] Result shows: COUNT > 10 (was 2 before)
- [ ] Result shows: Recent timestamp (not 40+ min old)
- [ ] Confirmed: PostgreSQL has fresh data ✅

**Expected Output**:
```
 total_rows |           latest           
------------+----------------------------
         15 | 2026-04-14 23:55:22.123456
(1 row)

 id  | timestamp | node_id | humidity | irrigation_status | ...
-----+-----------+---------+----------+-------------------+-----
  12 | 2026-04-14 23:55:22 | node1    |    45.5 |                 1 | ...
  11 | 2026-04-14 23:55:12 | node2    |    52.3 |                 0 | ...
  10 | 2026-04-14 23:55:02 | node1    |    44.2 |                 1 | ...
```

**If still 2 rows**:
- Check 4.3 (is Consumer inserting?)
- Consumer may take 30+ sec for first insert
- Try again after 2 more minutes

---

### 4.5: Verify Grafana displays data
```
Browser: http://192.168.100.97:3000
Login: admin / admin
Navigate to: Dashboard > Smart Irrigation
```

- [ ] Browser opened Grafana dashboard
- [ ] Dashboard is NOT showing "No data"
- [ ] Dashboard shows graphs/metrics
- [ ] Confirmed: Grafana is working ✅

**Expected Look**:
- Graphs with data points (not empty)
- Irrigation Status showing ON/OFF
- Humidity curves visible
- Recent timestamps (not stale)

**If still "No data"**:
- Check 4.4 (is PostgreSQL really updated?)
- Grafana may cache, try refresh (F5)
- Check dashboard query: Should include `iot_smart_irrigation_raw`
- If query is custom, may need adjustment

---

### 4.6: Verify Streamlit Cloud mode works
```bash
# If you have streamlit running:
# Browser: http://192.168.100.66:8501 (or your URL)

# Otherwise, test connection:
python3 -c "
import psycopg2
conn = psycopg2.connect('host=192.168.100.97 user=airflow password=airflow dbname=airflow')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM iot_smart_irrigation_raw')
print(f'✅ PostgreSQL connection OK, {cur.fetchone()[0]} rows')
cur.close()
conn.close()
"
```

- [ ] I ran the test
- [ ] Result shows: No timeout/connection error
- [ ] Result shows: Count > 10
- [ ] Confirmed: Streamlit Cloud mode should work ✅

---

## PHASE 5: FINAL VERIFICATION (Sanity check)

### 5.1: Run full health check
```bash
echo "=== PostgreSQL Status ===" && \
docker exec postgres psql -U airflow -d airflow \
  -c "SELECT COUNT(*) as total_rows FROM iot_smart_irrigation_raw;" && \
echo "=== Kafka Topics ===" && \
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 && \
echo "=== Consumer Status ===" && \
docker ps | findstr consumer && \
echo "=== RPi Data Logger ===" && \
ssh pi@192.168.100.66 "ps aux | grep '[d]ata_logger' | head -1"
```

- [ ] I ran the full health check
- [ ] PostgreSQL shows: >10 rows
- [ ] Kafka shows: iot_smart_irrigation topic
- [ ] Consumer shows: UP status
- [ ] RPi shows: data_logger_NEW.py running

**All checks passed?** → ✅ **FIX SUCCESSFUL**

---

## SUMMARY: Mark Your Progress

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FIX PROGRESS TRACKER                             │
├──────────────────────────────┬────────┬──────┬─────────────────────────┤
│ Phase                        │ Status │ Time │ Completed              │
├──────────────────────────────┼────────┼──────┼─────────────────────────┤
│ Phase 0: Pre-Audit           │ [ ]    │  2m  │ ☐ 4/4 items done       │
│ Phase 1: Diagnosis           │ [ ]    │  5m  │ ☐ 4/4 items done       │
│ Phase 2: Root Cause          │ [ ]    │  5m  │ ☐ 2/2 items done       │
│ Phase 3: Apply Fix           │ [ ]    │  7m  │ ☐ 5/5 items done       │
│ Phase 4: Verification        │ [ ]    │  8m  │ ☐ 6/6 items done       │
│ Phase 5: Health Check        │ [ ]    │  3m  │ ☐ 4/4 items done       │
├──────────────────────────────┼────────┼──────┼─────────────────────────┤
│ TOTAL                        │        │ 30m  │ ☐ 25/25 DONE = SUCCESS │
└──────────────────────────────┴────────┴──────┴─────────────────────────┘
```

---

## ✅ SUCCESS CRITERIA

- [ ] PostgreSQL count: > 10 (was 2)
- [ ] PostgreSQL latest timestamp: Current (was 40+ min old)
- [ ] Kafka topic: Has messages
- [ ] Consumer logs: Show "Received" + "INSERT"
- [ ] Grafana dashboard: NOT showing "No data"
- [ ] Grafana graphs: Displaying data
- [ ] Streamlit Cloud: NOT timing out
- [ ] No error messages in any logs

**If all 8 items are checked**: ✅ **FIX IS SUCCESSFUL**

---

## 🎯 What To Do Next (After Success)

### Optional: Cleanup old scripts
```bash
# On RPi:
ssh pi@192.168.100.66 "mv data_logger.py data_logger_OLD.py"

# On Desktop:
cd codes/
Move data_logger.py to data_logger_OLD.py
Move app.py to app_OLD.py
```

- [ ] Cleanup completed (optional but recommended)

### Optional: Add systemd service for auto-restart
```bash
ssh pi@192.168.100.66 << 'EOF'
sudo tee /etc/systemd/system/data-logger.service > /dev/null <<'SERVICE'
[Unit]
Description=Data Logger for Smart Irrigation
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/data_logger_NEW.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl enable data-logger
sudo systemctl start data-logger
sudo systemctl status data-logger
EOF
```

- [ ] Systemd service setup (optional, but highly recommended)

---

## 📊 Time Summary

| Phase | Time | Status |
|-------|------|--------|
| Diagnosis | 10m | ☐ |
| Fix Applied | 7m | ☐ |
| Verification | 8m | ☐ |
| Health Check | 3m | ☐ |
| **TOTAL** | **28m** | ☐ |

**Estimated completion**: You are here → [████████░░░░░░░░░░░░░░░] 40%

---

## 📞 If Something Goes Wrong

1. **PostgreSQL still shows 2 rows?**
   - Go back to 4.4
   - Wait 5 more minutes
   - Try the query again

2. **Kafka shows timeout?**
   - Go back to 4.2
   - Check that 3.4 completed successfully
   - Check MQTT on RPi: `mosquitto_sub -h localhost -t "irrigation/soil/#"`

3. **Consumer logs are empty?**
   - Go back to 4.3
   - Wait longer for logs to appear
   - Check Consumer is running: `docker ps | findstr consumer`

4. **Grafana still says "No data"?**
   - Check 4.5 PostgreSQL has data
   - Refresh Grafana browser (F5)
   - Check query in dashboard (should be `iot_smart_irrigation_raw`)

5. **Still stuck?**
   - Read DEPLOYMENT_FIX_15MIN.md Troubleshooting section
   - Or contact support with outputs of commands in Phase 5

---

**Good luck! You're almost done! 🚀**

Last checkpoint: Section 4.4 (PostgreSQL has new data?)

If yes → Continue to Grafana check (4.5)  
If no → Wait 2 more minutes, then retry 4.4
