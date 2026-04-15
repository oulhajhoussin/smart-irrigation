# 📋 DATA HOMOGENEITY FIX - DEPLOYMENT GUIDE

**Date** : 14/04/2026  
**Status** : 🚀 Ready to Deploy

---

## 🎯 OBJECTIF

Fixer l'incohérence des données entre Mode Cloud (SQL) et Mode Secours (CSV).

### Problèmes Résolus
- ✅ **Timestamps Unix** → ISO format lisible
- ✅ **Champs vides** → Tous les 18 champs remplis
- ✅ **Parsing CSV** → Conversion datetime

---

## 📂 FICHIERS MODIFIÉS

### 1️⃣ data_logger.py (Ligne 1-155)
**Changements** :
- Import `datetime` (ligne 7)
- Timestamp ISO au lieu d'Unix (ligne 110)
- Extraction complète des champs MQTT (lignes 113-121)
- Row complète 18 colonnes (lignes 137-156)

**Impact** : 
- ✅ CSV reçoit timestamps lisibles
- ✅ CSV contient tous les champs
- ✅ Données complètes dès la source

### 2️⃣ app.py (Lignes 137-155)
**Changements** :
- Ajouter `parse_dates=['timestamp']`
- Ajouter `infer_datetime_format=True`
- Formater timestamps ISO en affichage

**Impact** :
- ✅ Timestamps CSV parsés correctement
- ✅ Affichage identique à PostgreSQL
- ✅ Cohérence visuelle complète

---

## 🔄 PROCESSUS DE DÉPLOIEMENT

### Étape 1 : Télécharger les fichiers fixes
```bash
# Sur votre PC
scp codes/data_logger.py pi@192.168.100.66:/home/pi/
scp codes/app.py pi@192.168.100.66:/home/pi/
```

### Étape 2 : Arrêter les services
```bash
# Sur le Raspberry Pi
ssh pi@192.168.100.66

# Arrêter data_logger
pkill -f "python.*data_logger.py"

# Arrêter Streamlit
pkill -f "streamlit run"
```

### Étape 3 : Supprimer l'ancien CSV
```bash
# Sur le Raspberry Pi
rm /home/pi/data_logger.csv
# Cela efface l'ancien fichier avec timestamps Unix
# Le nouveau data_logger.py créera un nouveau CSV avec ISO timestamps
```

⚠️ **IMPORTANT** : Sinon le nouveau code continuera à lire l'ancien format

### Étape 4 : Relancer les services
```bash
# Relancer data_logger
cd /home/pi
python3 data_logger.py &

# Attendre 30 secondes que des données arrivent
sleep 30

# Relancer Streamlit
streamlit run app.py
```

### Étape 5 : Valider
```
1. Ouvrir Streamlit → http://192.168.100.66:8501
2. Vérifier Mode Cloud (SQL) :
   - Timestamps en format : "2026-04-14 17:19:56" ✅
   - Tous les champs remplis ✅
   - Graphes s'affichent ✅

3. Tester Mode Secours :
   - Arrêter Docker : docker compose down
   - Vérifier Streamlit affiche "Local (CSV) - Mode Secours 🛡️"
   - Vérifier timestamps lisibles ✅
   - Vérifier champs remplis ✅
   - Vérifier cohérence avec Mode Cloud ✅

4. Relancer Docker : docker compose up -d
   - Vérifier basculage automatique vers Cloud ✅
```

---

## 📊 RÉSULTATS ATTENDUS

### Avant Fix ❌

**Mode Cloud (SQL)** :
```
timestamp         | soil_pct | rssi | snr | jitter_ms | battery
2026-04-14 17:19 | 15.0     | -95  | 7.5 | 0.5       | 85%
```

**Mode Secours (CSV)** :
```
timestamp          | soil_pct | rssi | snr | jitter_ms | battery
1771978758.14     | 15.0     | (vide) | (vide) | (vide) | (vide)
❌ Illisible! ❌ Incomplet!
```

### Après Fix ✅

**Mode Cloud (SQL)** :
```
timestamp         | soil_pct | rssi | snr | jitter_ms | battery
2026-04-14 17:19 | 15.0     | -95  | 7.5 | 0.5       | 85%
```

**Mode Secours (CSV)** :
```
timestamp         | soil_pct | rssi | snr | jitter_ms | battery
2026-04-14 17:19 | 15.0     | -95  | 7.5 | 0.5       | 85%
✅ Identique! ✅ Complet!
```

---

## 🧪 TESTS DE VALIDATION

### Test 1 : Nouveau CSV généré
```bash
# Vérifier que data_logger.py écrit le bon format
tail -5 /home/pi/data_logger.csv

# Expected output :
# timestamp,node_id,counter,soil_pct,raw_data,payload_bytes,rssi,snr,...
# 2026-04-14T17:19:56.123456,node1,1,15.0,N01,1,15,48,-95,7.5,0.5,...
#                           ↑ ISO format!
```

### Test 2 : Mode Cloud affiche bien
```bash
# Streamlit doit afficher timestamps lisibles
# "2026-04-14 17:19:56" ✅

# Chercher "soil_pct" dans graphes
# Doit afficher : 15.0%, -95 dBm, 85%, etc.
```

### Test 3 : Mode CSV affiche identique
```bash
# Arrêter Docker
docker compose down

# Streamlit bascule en Mode Secours
# "Status: Local (CSV) - Mode Secours 🛡️"

# Vérifier timestamps lisibles
# "2026-04-14 17:19:56" ✅

# Vérifier champs visibles
# soil_pct, rssi, snr, jitter, battery, etc. ✅
```

### Test 4 : Failover automatique
```bash
# Docker arrêté → Mode Secours
docker compose down
# Vérifier CSV mode ✅

# Relancer Docker
docker compose up -d

# Attendre 10 secondes
sleep 10

# Vérifier basculage automatique
# "Status: Cloud (SQL)" ✅
# Pas d'intervention manuelle ✅
```

---

## 🔍 TROUBLESHOOTING

### Si timestamps restent au format Unix
```bash
# Cause : Ancien CSV encore présent
# Solution :
rm /home/pi/data_logger.csv
pkill -f "python.*data_logger.py"
python3 /home/pi/data_logger.py &
```

### Si champs restent vides
```bash
# Cause : data_logger.py n'envoie pas les valeurs
# Vérifier que MQTT envoie bien :
mosquitto_sub -h 192.168.100.66 -t "irrigation/soil/#" | head -5

# Expected JSON :
# {"raw":"N01,1,15,...","rssi":-95,"snr":7.5,"jitter_ms":0.5, ...}

# Si manquant : corriger le firmware TTGO/Arduino
```

### Si Streamlit plante au parsing
```bash
# Cause : Mélange old/new format CSV
# Solution :
rm /home/pi/data_logger.csv  # ← Effacer complètement
pkill -f "streamlit"
streamlit run /home/pi/app.py
```

---

## 📋 CHECKLIST PRÉ-DÉPLOIEMENT

- [ ] data_logger.py téléchargé sur Pi
- [ ] app.py téléchargé sur Pi
- [ ] Ancien data_logger.csv supprimé
- [ ] data_logger.py redémarré
- [ ] Streamlit redémarré
- [ ] Vérification Mode Cloud (timestamps lisibles)
- [ ] Test Mode Secours (docker down)
- [ ] Vérification cohérence Cloud/CSV
- [ ] Test failover automatique (docker up)
- [ ] Tous graphes s'affichent correctement
- [ ] Aucun erreur dans console Streamlit
- [ ] Aucun erreur dans console data_logger.py

---

## 🎯 RÉSUMÉ DES CHANGEMENTS

| Fichier | Ligne | Avant | Après | Raison |
|---------|-------|-------|-------|--------|
| data_logger.py | 7 | (import) | `from datetime import datetime` | ISO timestamps |
| data_logger.py | 110 | `time.time()` | `datetime.now().isoformat()` | Format lisible |
| data_logger.py | 113-121 | Extraction partielle | Extraction complète MQTT | Tous champs |
| data_logger.py | 137-156 | 8 champs vides | 18 champs remplis | Données complètes |
| app.py | 142 | `read_csv()` basique | `parse_dates=['timestamp']` | Datetime parsing |
| app.py | 145 | (aucun) | `.strftime()` format | Affichage cohérent |

---

## ✅ SUCCESS CRITERIA

Après déploiement, le système doit avoir :

- ✅ Timestamps identiques Cloud/CSV (format : "2026-04-14 HH:MM:SS")
- ✅ Tous les 18 champs remplis dans les deux modes
- ✅ Graphes identiques entre Cloud et CSV
- ✅ Failover automatique <5 secondes
- ✅ Aucune perte de données
- ✅ Mode Secours aussi utile que Mode Cloud

---

**Status** : ✅ READY FOR DEPLOYMENT

**Next Step** : Execute deployment process above
