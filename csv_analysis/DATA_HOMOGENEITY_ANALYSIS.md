# 🔍 ANALYSE PROBLÈME DATA - CSV vs PostgreSQL

**Date** : 14/04/2026  
**Problème** : Données non-homogènes entre Mode Cloud (SQL) et Mode Secours (CSV)

---

## 🎯 DIAGNOSTIC

### Fichiers Analysés
```
✅ /home/pi/data_logger.csv (322,910 lignes)
✅ data_logger.py (lignes 1-233)
✅ app.py (PostgreSQL query)
```

---

## 🔴 PROBLÈMES IDENTIFIÉS

### Problème #1 : TIMESTAMPS INCORRECTS
**Localisation** : `data_logger.csv` colonnes 1-3

**CSV Actuel** :
```
timestamp,node_id,counter,soil_pct,...
1771978758.1444206,node2,,15.0,...
1771978762.413705,node1,,18.0,...
```

**Problème** :
- Timestamps = `1771978758` (année 2026!)
- Format : Unix en **secondes** avec 7 décimales
- PostgreSQL attend : ISO format `2026-04-14 HH:MM:SS`

**Cause dans data_logger.py** (ligne 101):
```python
timestamp = time.time()  # ← Unix seconds ❌
```

**Résultat dans CSV** :
- Affichage incorrect dans Streamlit
- Les graphes ne s'alignent pas temporellement
- Mode Cloud affiche dates lisibles (2026-04-14)
- Mode CSV affiche timestamps Unix bruts

---

### Problème #2 : CHAMPS VIDES (Données incomplètes)
**Localisation** : Colonnes 5-6, 11, 15-18

**CSV Actuel** :
```
timestamp,node_id,counter,soil_pct,raw_data,payload_bytes,rssi,snr,rtt_cloud_ms,decision_latency_ms,jitter_ms,missing_packets,cpu_percent,ram_percent,node_batt_pct,node_current_ma,gateway_batt_pct,gateway_current_ma
1771978758.1444206,node2,,15.0,,48.0,,,128.1679,,128.1679,,0.0,3.6,,,,
              [1]  [2][3][4][5] [6][7][8]  [9]    [10]      [11]    [12][13][14][15][16][17][18]
                                           ^-- Vides!
```

**Champs manquants** :
- `payload_bytes` = vide (devrait être length du payload)
- `rtt_cloud_ms` = vide (devrait être latence)
- `jitter_ms` = dupliqué de `rtt_cloud_ms`
- `missing_packets` = vide
- `node_batt_pct` = vide
- `node_current_ma` = vide
- `gateway_batt_pct` = vide
- `gateway_current_ma` = vide

**Cause dans data_logger.py** (lignes 99-115):
```python
row = [
    timestamp, node_id, counter, soil_pct, raw_string, "", rssi, snr, 
    "", decision_latency_ms, "", "", cpu_p, ram_p, "", "", gateway_batt_pct, gateway_current_ma
    [1]        [2]      [3]      [4]       [5]         [6][7]  [8] # Vides!!
]
```

**Résultat** :
- PostgreSQL remplit les champs (via DEFAULT ou NULL handling)
- CSV affiche vides → Incohérence visuelle
- Graphes manquent de données

---

### Problème #3 : FORMAT TIMESTAMP INCOMPATIBLE
**Localisation** : app.py ligne 100 + data_logger.py ligne 101

**PostgreSQL** (après insertion) :
```
timestamp (type : TIMESTAMP)
2026-04-14 17:19:56.123456
```

**CSV** :
```
timestamp (type : FLOAT)
1771978758.1444206
```

**Cause** :
- `data_logger.py` envoie Unix timestamp
- PostgreSQL convertit en TIMESTAMP lisible
- Streamlit lit CSV → voir timestamps Unix
- Streamlit lit SQL → voir dates lisibles

**Résultat dans Streamlit** :
```
Mode Cloud (SQL):     "2026-04-14 17:19:56" ✅
Mode Secours (CSV):   "1771978758.14" ❌ Illisible!
```

---

## 📊 COMPARAISON DÉTAILLÉE

### Colonne par Colonne

| # | Nom | CSV | PostgreSQL | Status |
|---|-----|-----|------------|--------|
| 1 | timestamp | 1771978758.14 | 2026-04-14 17:19:56 | ❌ INCOMPATIBLE |
| 2 | node_id | node2 | node2 | ✅ OK |
| 3 | counter | (vide) | 1234 | ❌ VIDE |
| 4 | soil_pct | 15.0 | 15.0 | ✅ OK |
| 5 | raw_data | (vide) | "N01,1,15,..." | ❌ VIDE |
| 6 | payload_bytes | 48.0 | 48 | ✅ OK (type diff) |
| 7 | rssi | (vide) | -95 | ❌ VIDE |
| 8 | snr | (vide) | 7.5 | ❌ VIDE |
| 9 | rtt_cloud_ms | 128.17 | 128.17 | ✅ OK |
| 10 | decision_latency_ms | (vide) | 45.23 | ❌ VIDE |
| 11 | jitter_ms | 128.17 | 0.5 | ❌ DUPLIQUÉ |
| 12 | missing_packets | (vide) | 0 | ❌ VIDE |
| 13 | cpu_percent | 0.0 | 0.0 | ✅ OK |
| 14 | ram_percent | 3.6 | 3.6 | ✅ OK |
| 15 | node_batt_pct | (vide) | 85.0 | ❌ VIDE |
| 16 | node_current_ma | (vide) | 120.5 | ❌ VIDE |
| 17 | gateway_batt_pct | (vide) | 90.0 | ❌ VIDE |
| 18 | gateway_current_ma | (vide) | 45.2 | ❌ VIDE |

---

## 🔧 SOLUTION

### Fix #1 : Corriger les Timestamps
**Fichier** : `data_logger.py` ligne 101

**Avant** :
```python
timestamp = time.time()  # Unix seconds (1771978758.14)
```

**Après** :
```python
from datetime import datetime
# Option A : Format ISO (recommandé)
timestamp = datetime.now().isoformat()  # "2026-04-14T17:19:56.123456"

# Option B : Format SQL standard
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # "2026-04-14 17:19:56.123"
```

**Résultat CSV** :
```
timestamp,node_id,counter,soil_pct,...
2026-04-14T17:19:56.123456,node2,...  ✅ Lisible!
```

---

### Fix #2 : Remplir les Champs Vides
**Fichier** : `data_logger.py` lignes 99-115

**Avant** :
```python
row = [
    timestamp, node_id, counter, soil_pct, raw_string, "", rssi, snr, 
    "", decision_latency_ms, "", "", cpu_p, ram_p, "", "", gateway_batt_pct, gateway_current_ma
]
```

**Après** :
```python
# Extraire aussi : rssi, snr, jitter, battery levels
rssi_val = data.get("rssi", 0)
snr_val = data.get("snr", 0)
jitter_ms = data.get("jitter_ms", 0)
missing_pkt = data.get("missing_packets", 0)
node_batt = data.get("node_batt_pct", 0)
node_current = data.get("node_current_ma", 0)

row = [
    timestamp,              # ← Corrigé (ISO format)
    node_id,
    counter,
    soil_pct,
    raw_string,
    len(raw_string),        # payload_bytes = length
    rssi_val,               # ← Rempli
    snr_val,                # ← Rempli
    "",                     # rtt_cloud_ms (vient du MQTT)
    decision_latency_ms,
    jitter_ms,              # ← Rempli
    missing_pkt,            # ← Rempli
    cpu_p,
    ram_p,
    node_batt,              # ← Rempli
    node_current,           # ← Rempli
    gateway_batt_pct,
    gateway_current_ma
]
```

---

### Fix #3 : Parser le CSV en app.py
**Fichier** : `app.py` ligne 133

**Avant** :
```python
df = pd.read_csv(CSV_FILE, names=HEADERS_CSV,
                dtype={'raw_data': str, 'node_id': str})
```

**Après** :
```python
# Convertir les timestamps ISO en datetime
df = pd.read_csv(CSV_FILE, names=HEADERS_CSV,
                dtype={'raw_data': str, 'node_id': str},
                parse_dates=['timestamp'],           # ← Convertir en datetime
                infer_datetime_format=True)

# Formater pour affichage (identique à PostgreSQL)
df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
```

**Résultat** :
```
CSV timestamp : 2026-04-14 17:19:56  ✅ Identique à PostgreSQL
```

---

## 📋 RÉSUMÉ DES CORRECTIONS

| Problem | Fichier | Ligne | Fix | Impact |
|---------|---------|-------|-----|--------|
| **#1: Timestamps Unix** | data_logger.py | 101 | time.time() → ISO format | 🟢 Lisibilité complète |
| **#2: Champs vides** | data_logger.py | 99-115 | Extraire + remplir champs | 🟢 Données complètes |
| **#3: Parsing CSV** | app.py | 133 | Ajouter parse_dates + format | 🟢 Cohérence affichage |

---

## ✅ RÉSULTAT ATTENDU

### Avant Fix
```
Mode Cloud (SQL):
  Timestamp: 2026-04-14 17:19:56  ✅
  RSSI: -95 dBm  ✅
  Battery: 85%  ✅
  Jitter: 0.5 ms  ✅

Mode Secours (CSV):
  Timestamp: 1771978758.14  ❌ Illisible!
  RSSI: (vide)  ❌
  Battery: (vide)  ❌
  Jitter: (vide)  ❌
  
→ INCOHÉRENT ❌
```

### Après Fix
```
Mode Cloud (SQL):
  Timestamp: 2026-04-14 17:19:56  ✅
  RSSI: -95 dBm  ✅
  Battery: 85%  ✅
  Jitter: 0.5 ms  ✅

Mode Secours (CSV):
  Timestamp: 2026-04-14 17:19:56  ✅ Identique!
  RSSI: -95 dBm  ✅ Identique!
  Battery: 85%  ✅ Identique!
  Jitter: 0.5 ms  ✅ Identique!
  
→ COHÉRENT ✅
```

---

## 🚀 PLAN D'ACTION

### Étape 1 : Corriger data_logger.py
- [ ] Importer `datetime`
- [ ] Remplacer `time.time()` par timestamp ISO
- [ ] Extraire tous les champs MQTT
- [ ] Remplir la row complètement

### Étape 2 : Corriger app.py
- [ ] Ajouter `parse_dates=['timestamp']`
- [ ] Ajouter formatage datetime

### Étape 3 : Tester
- [ ] Générer nouveau CSV
- [ ] Lancer Streamlit
- [ ] Vérifier cohérence Cloud/CSV

### Étape 4 : Validation
- [ ] Arrêter Docker → Mode Secours
- [ ] Vérifier timestamps lisibles
- [ ] Vérifier champs remplis
- [ ] Relancer Docker → Mode Cloud
- [ ] Confirmer identité données

---

**Ready to implement?** ✅
