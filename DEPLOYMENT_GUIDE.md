# 🚀 GUIDE DE DÉPLOIEMENT RAPIDE

## Situation actuelle
- ❌ Grafana: "No data" (table vide ou format incompatible)
- ⚠️ Streamlit: Mode CSV fallback (Cloud timeout)
- 🔴 Kafka: Reçoit les messages mais Consumer ne les insère pas
- 📊 CSV RPi: 18 colonnes (manque irrigation_status, rtt_cloud_ms vide)

## Cause racine
Le CSV (18 cols) ≠ DB schema (20 cols). Le consumer attend `irrigation_status` mais ne le reçoit pas.

---

## ⚡ DÉPLOIEMENT IMMÉDIAT (5 minutes)

### Étape 1: Backup des fichiers actuels
```bash
# Sur RPi (SSH):
ssh pi@192.168.100.66

# Backups
cp /home/pi/data_logger.py /home/pi/data_logger.py.BACKUP_$(date +%Y%m%d_%H%M%S)
cp /home/pi/app.py /home/pi/app.py.BACKUP_$(date +%Y%m%d_%H%M%S)
```

### Étape 2: Copier les nouveaux fichiers

**Option A: Via SCP (depuis Windows PowerShell)**
```powershell
# Ouvrir PowerShell sur le dossier contenant les fichiers NEW

# Copier data_logger
scp .\data_logger_NEW.py pi@192.168.100.66:/home/pi/data_logger.py

# Copier app
scp .\app_NEW.py pi@192.168.100.66:/home/pi/app.py

# Vérifier copie
ssh pi@192.168.100.66 ls -la /home/pi/data_logger*.py
```

**Option B: Via GitHub (si vous utilisez git)**
```bash
# Pusher les fichiers NEW vers branche feature
git add data_logger_NEW.py app_NEW.py
git commit -m "fix: Add irrigation_status & rtt_cloud_ms to CSV/Kafka"
git push

# Sur RPi: pull et remplacer
ssh pi@192.168.100.66
cd ~/projet-dataops-mlops
git pull
cp data_logger_NEW.py /home/pi/data_logger.py
cp app_NEW.py /home/pi/app.py
```

### Étape 3: Redémarrer les services
```bash
# Sur RPi (SSH):

# 1. Redémarrer data_logger (qui écrit le CSV et envoie Kafka)
sudo systemctl restart iot_logger

# 2. Attendre 3 secondes
sleep 3

# 3. Vérifier que le service est actif
systemctl is-active iot_logger
# Retour attendu: "active"

# 4. Voir les nouveaux logs
journalctl -u iot_logger -n 20 --no-pager
```

### Étape 4: Vérifier les données
```bash
# Sur RPi: afficher les 2 premières lignes du CSV
head -2 /home/pi/data_logger.csv

# Résultat attendu:
# timestamp,node_id,counter,soil_pct,irrigation_status,raw_data,...
#                                     ↑ NOUVELLE colonne
# 2026-04-14T21:55:34.123,node1,15226,92,1,"NODE1,15226...",18,-40,...
#                                      ↑ Valeur 0 ou 1
```

### Étape 5: Redémarrer Consumer Docker
```bash
# Sur Windows (Docker PC):
cd c:\Users\GODFATHER\Desktop\dataset\projet-dataops-mlops

docker compose restart data-consumer

# Attendre que le consumer se reconnecte à Kafka
timeout /t 3

# Vérifier les logs
docker logs data-consumer --tail 30
```

### Étape 6: Vérifier PostgreSQL
```bash
# Depuis Windows PowerShell:
# Lancer psql via Docker

docker exec -it projet-dataops-mlops-postgres-1 psql -U airflow -d airflow -c "SELECT COUNT(*), MAX(timestamp) FROM iot_smart_irrigation_raw;"

# Résultat attendu:
# count | max
# ------+---------------------------
#   456 | 2026-04-14 21:55:34.123
#   ↑ NOMBRE > 0 (données arrivent!)
```

### Étape 7: Redémarrer Streamlit
```bash
# Sur RPi (SSH):
# Streamlit va auto-reload, mais on peut forcer:

systemctl restart iot_streamlit

# Ou simplement aller sur http://192.168.100.66:8501
# L'app va chercher à récupérer les données
```

### Étape 8: Vérifier Grafana
```
- Aller sur http://192.168.100.97:3000
- Ouvrir dashboard "Smart Irrigation — Edge/Fog/AI DataOps"
- Les panneaux devraient afficher les données
- Si encore vide, cliquer sur "Refresh" (F5)
```

---

## ✅ CHECKLIST DE VALIDATION

```
Data Flow Validation:
  [ ] CSV RPi a 19 colonnes (irrigation_status visible en col 5)
  [ ] irrigation_status contient 0 ou 1 (pas vide)
  [ ] rtt_cloud_ms contient des valeurs en ms (ex: 23.5, pas vide)
  [ ] Consumer logs montrent "INSERT INTO iot_smart_irrigation_raw"
  [ ] PostgreSQL COUNT > 0 (données insérées)
  
Application Validation:
  [ ] Streamlit affiche "Cloud (SQL) ✅" (pas "CSV Fallback")
  [ ] Badge "Déclenchements Pompes" affiche nombre > 0
  [ ] Graphiques Humidité montrent les courbes
  [ ] État Pompe (Zone A/B) affiche ON/OFF basé sur irrigation_status
  
Grafana Validation:
  [ ] Variable $Node retourne [node1, node2]
  [ ] Graphique "Humidity timeline" affiche courbes
  [ ] Graphique "Irrigation decisions" affiche barres
  [ ] Tous les panneaux ont des données (pas "No data")
```

---

## 🔍 TROUBLESHOOTING

### Si CSV n'a toujours que 18 colonnes:
```bash
# Vérifier que data_logger.py a bien été remplacé
grep -c "irrigation_status" /home/pi/data_logger.py
# Doit retourner: 3+ (plusieurs occurrences)

# Si 0, c'est que l'ancien fichier est toujours utilisé
cat /home/pi/data_logger.py | head -20 | grep "HEADERS ="
# Doit afficher 19 éléments dans la liste
```

### Si Consumer ne démarre pas:
```bash
docker logs data-consumer

# Chercher messages d'erreur comme:
# - "Connection refused" → Kafka pas accessible
# - "psycopg2" → PostgreSQL pas accessible
# - "KeyError" → Champ manquant dans payload Kafka

# Pour forcer rejeu depuis le début:
docker exec data-consumer kafka-consumer-groups --bootstrap-server kafka:9092 --reset-offsets --all-offsets --group soil_moisture_group --execute --to-earliest
```

### Si Grafana affiche encore "No data":
```bash
# 1. Vérifier que les données sont vraiment dans la DB
docker exec projet-dataops-mlops-postgres-1 psql -U airflow -d airflow \
  -c "SELECT timestamp, node_id, irrigation_status FROM iot_smart_irrigation_raw LIMIT 5;"

# 2. Forcer refresh des données dans Grafana
# → Cliquer sur "Refresh" (F5) ou attendre 5s

# 3. Vérifier la requête du panel
# → Dashboard → Edit → Panel → Inspect → Data
# Cela montrera exactement ce que SQL retourne
```

### Si Streamlit affiche "Local (CSV) 🛡️":
```bash
# C'est le mode fallback = PostgreSQL timeout
# Causes possibles:
# 1. Docker a crash (vérifier: docker ps)
# 2. Firewall bloque port 5432 (vérifier: telnet 192.168.100.97 5432)
# 3. PostgreSQL n'a pas redémarré (vérifier: docker logs postgres)

# Solution:
docker compose restart postgres
sleep 3
docker compose restart data-consumer
```

---

## 📊 RÉSULTATS ATTENDUS

**AVANT (Situation actuelle)**:
```
CSV: 18 cols (manque irrigation_status)
     ├─ irrigation/soil/node1: humidité 45% → CSV ligne 1
     └─ Graphique Grafana: ❌ No data

Streamlit:
     ├─ Status: "Local (CSV) 🛡️"
     ├─ Badge: 0 déclenchements (car comptage faux)
     └─ Graphique pompes: Vide
```

**APRÈS (Résultat du déploiement)**:
```
CSV: 19 cols (inclut irrigation_status=1)
     ├─ irrigation/soil/node1: humidité 45%, IA decision 1 → CSV ligne 1
     ├─ Kafka: Reçoit irrigation_status=1
     ├─ Consumer: INSERT iot_smart_irrigation_raw (20 champs)
     └─ Grafana: ✅ Affiche humidity=45%, pump=ON

Streamlit:
     ├─ Status: "Cloud (SQL) ✅"
     ├─ Badge: 456 déclenchements (comptage précis)
     └─ Graphique pompes: Affiche courbes ON/OFF cohérentes
```

---

## ⏱️ TIMING PRÉVU

| Étape | Durée | Action |
|-------|-------|--------|
| 1. Backups | 30s | cp des fichiers |
| 2. Copie fichiers | 1m | scp vers RPi |
| 3. Redémarrage data_logger | 10s | systemctl restart |
| 4. Attendre données | 15s | consumer reçoit messages |
| 5. Redémarrage consumer | 20s | docker restart |
| 6. Affichage Grafana | 10s | refresh F5 |
| **TOTAL** | **3-5 min** | ✅ Système restauré |

---

## 🎯 VALIDAÇÃO FINALE

Une fois que tout est déployé, dans **Streamlit** (http://192.168.100.66:8501):

1. Vérifier que "Status: **Cloud (SQL) ✅**" s'affiche
2. Vérifier que le badge "Déclenchements Pompes" affiche un nombre > 0
3. Vérifier que les graphiques affichent des courbes (pas vides)
4. Vérifier que Zone A/B affichent "IRRIGATION" ou "COUPÉ" (pas vide)

Si tous les ✅ s'affichent → **Déploiement réussi ! 🎉**

---

## 📞 SUPPORT

Si quelque chose ne fonctionne pas:

1. Vérifier les logs:
   ```bash
   # RPi data_logger
   journalctl -u iot_logger -n 50 --no-pager
   
   # Consumer Docker
   docker logs data-consumer -n 50
   
   # PostgreSQL
   docker logs postgres -n 50
   ```

2. Vérifier la connectivité:
   ```bash
   # Peut-on ping le Docker PC depuis RPi?
   ping -c 3 192.168.100.97
   
   # PostgreSQL accessible?
   psql -h 192.168.100.97 -U airflow -d airflow -c "SELECT 1;"
   ```

3. Vérifier les formats:
   ```bash
   # CSV headers correctes?
   head -1 /home/pi/data_logger.csv | tr ',' '\n' | nl
   
   # Doit afficher irrigation_status à la ligne 5
   ```

---

✅ **Prêt à déployer !**
