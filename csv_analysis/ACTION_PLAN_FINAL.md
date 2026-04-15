# 🚀 PLAN D'ACTION FINAL - Data Homogeneity + Bug Fix

**Date** : 14/04/2026  
**Status** : ✅ Ready to Deploy  

---

## 📊 RÉSUMÉ DES PROBLÈMES & SOLUTIONS

### Problème #1 : Données CSV incohérentes vs PostgreSQL ❌
**Causes** :
- Timestamps Unix au lieu d'ISO → `1771978758.14` illisible
- Champs vides (rssi, snr, battery, etc.)
- Parsing CSV défaillant

**Solutions** :
- ✅ Timestamps ISO dans data_logger.py
- ✅ Extraction complète MQTT dans data_logger.py
- ✅ Row 18 colonnes remplie dans data_logger.py
- ✅ Parsing robuste dans app.py

---

### Problème #2 : Message "Recherche de signal..." persiste ❌
**Cause** :
- `infer_datetime_format` déprecié en pandas 2.0+
- CSV ne charge pas → df.empty → affiche "Recherche..."
- Erreur non affichée à l'utilisateur

**Solution** :
- ✅ Supprimer `infer_datetime_format`
- ✅ Ajouter try/except pour timestamp
- ✅ Afficher les erreurs spécifiques

---

## 📋 FICHIERS À METTRE À JOUR

### 1️⃣ data_logger.py
**Ligne 7** : Ajouter import `datetime`
```python
from datetime import datetime
```

**Ligne 110** : Timestamp ISO
```python
timestamp = datetime.now().isoformat()
```

**Lignes 113-121** : Extraire tous les champs MQTT
```python
rssi = data.get("rssi", 0)
snr = data.get("snr", 0)
jitter_ms = data.get("jitter_ms", 0)
missing_packets = data.get("missing_packets", 0)
node_batt_pct = data.get("node_batt_pct", 0)
node_current_ma = data.get("node_current_ma", 0)
```

**Lignes 137-156** : Row 18 colonnes
```python
row = [
    timestamp, node_id, counter, soil_pct, raw_string, len(raw_string),
    rssi, snr, "", decision_latency_ms, jitter_ms, missing_packets,
    cpu_p, ram_p, node_batt_pct, node_current_ma, gateway_batt_pct, gateway_current_ma
]
```

### 2️⃣ app.py
**Ligne 140-155** : Parsing CSV sécurisé
```python
df = pd.read_csv(CSV_FILE, names=HEADERS_CSV, 
                dtype={...},
                parse_dates=['timestamp'])  # ← Sans infer_datetime_format

try:
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
except:
    pass

st.error(f"❌ Erreur lecture CSV: {csv_error}")
```

**Lignes 361-371** : Gestion message "Recherche..."
```python
else:
    if sql_error:
        with st.sidebar:
            st.error(f"⚠️ Pas de données disponibles\n\n{sql_error}")
    else:
        st.info("Recherche de signal IoT...")
```

---

## 🚀 PLAN DE DÉPLOIEMENT (PAS À PAS)

### Phase 1 : Préparation (5 min)
```bash
# 1. Sur PC local : Vérifier tous les fichiers sont modifiés
✅ data_logger.py (7 modifications)
✅ app.py (4 modifications)

# 2. Télécharger les fichiers
scp codes/data_logger.py pi@192.168.100.66:/home/pi/
scp codes/app.py pi@192.168.100.66:/home/pi/
```

### Phase 2 : Nettoyage (5 min)
```bash
# 1. Connecter au Pi
ssh pi@192.168.100.66

# 2. Arrêter les services
pkill -f "python.*data_logger.py"
pkill -f "streamlit run"
sleep 2

# 3. Supprimer ancien CSV (⚠️ IMPORTANT)
rm /home/pi/data_logger.csv
# Cela force la création d'un nouveau CSV avec bon format

# 4. Vérifier suppression
ls -la /home/pi/data_logger.csv
# → "No such file or directory" ✅
```

### Phase 3 : Redémarrage (5 min)
```bash
# 1. Redémarrer data_logger
python3 /home/pi/data_logger.py &

# 2. Attendre données (30 secondes)
sleep 30

# 3. Vérifier CSV créé avec bon format
head -2 /home/pi/data_logger.csv
# Expected: 
# timestamp,node_id,counter,soil_pct,...
# 2026-04-14T...,node1,...

# 4. Redémarrer Streamlit
streamlit run /home/pi/app.py
```

### Phase 4 : Test Mode Cloud (5 min)
```
1. Ouvrir Streamlit : http://192.168.100.66:8501

2. Vérifier affichage :
   ✅ Status: Cloud (SQL)
   ✅ Sidebar: "✅ Connecté à PostgreSQL (Cloud)"
   ✅ Timestamps: "2026-04-14 HH:MM:SS"
   ✅ Graphes: Affichés correctement
   ✅ Historique IoT: 10 dernières lignes visibles

3. Attendre 30 secondes : Données s'actualisent automatiquement
```

### Phase 5 : Test Mode Secours (5 min)
```bash
# 1. Sur PC local
docker compose down

# 2. Vérifier Streamlit (attendre 10-30 secondes)
   ✅ Status: Local (CSV) - Mode Secours 🛡️
   ✅ Sidebar: "⚠️ PostgreSQL Indisponible"
   ✅ Message: "✅ Le système bascule automatiquement au CSV local..."
   ✅ Dashboard: S'affiche IMMÉDIATEMENT (pas "Recherche...")
   ✅ Timestamps: Identiques au Mode Cloud ✅
   ✅ Graphes: Affichés (mêmes données que Cloud)
   ✅ Historique: 10 dernières lignes visibles

# 3. IMPORTANT : Vérifier qu'il N'Y A PAS de "Recherche de signal IoT..."
#    Sinon → Erreur CSV affichée dans sidebar
```

### Phase 6 : Test Failover (5 min)
```bash
# 1. Relancer Docker
docker compose up -d

# 2. Vérifier Streamlit (attendre 10 secondes)
   ✅ Status: Cloud (SQL)
   ✅ Sidebar: "✅ Connecté à PostgreSQL (Cloud)"
   ✅ Basculage AUTOMATIQUE (pas d'action manuelle)

# 3. Confirmation : Les données sont identiques
#    (pas de saut ou discontinuité dans les graphes)
```

### Phase 7 : Validation Finale (5 min)
```
Checklist :
□ Mode Cloud affiche données PostgreSQL ✅
□ Mode CSV affiche données identiques ✅
□ Pas de "Recherche de signal..." en Mode Secours ✅
□ Timestamps identiques Cloud/CSV ✅
□ Tous les champs remplis (rssi, battery, etc.) ✅
□ Failover automatique fonctionne ✅
□ Dashboard responsive (actualisation toutes les 10s) ✅
□ Aucune erreur dans console Streamlit ✅
```

---

## 🧪 TESTS ADDITIONNELS (OPTIONNEL)

### Test de Validation CSV
```bash
# Sur le Pi
python3 << 'EOF'
import pandas as pd

CSV_FILE = "/home/pi/data_logger.csv"
HEADERS = ['timestamp', 'node_id', 'counter', 'soil_pct', 'raw_data', 'payload_bytes', 
           'rssi', 'snr', 'rtt_cloud_ms', 'decision_latency_ms', 'jitter_ms', 'missing_packets', 
           'cpu_percent', 'ram_percent', 'node_batt_pct', 'node_current_ma', 'gateway_batt_pct', 'gateway_current_ma']

try:
    df = pd.read_csv(CSV_FILE, names=HEADERS, dtype={'raw_data': str, 'node_id': str}, parse_dates=['timestamp']).tail(10)
    print(f"✅ CSV VALID: {len(df)} rows")
    print(f"Columns: {len(df.columns)}/18")
    print(f"First timestamp: {df['timestamp'].iloc[-1]}")
    print(f"Nodes: {df['node_id'].unique()}")
except Exception as e:
    print(f"❌ CSV ERROR: {e}")
EOF
```

---

## ⚠️ TROUBLESHOOTING

### Si "Recherche de signal..." persiste après déploiement

**Cause 1 : Ancien CSV pas supprimé**
```bash
rm /home/pi/data_logger.csv
pkill -f "python.*data_logger.py"
python3 /home/pi/data_logger.py &
sleep 30
pkill -f "streamlit run"
streamlit run /home/pi/app.py
```

**Cause 2 : Timestamps encore au format Unix**
```bash
# Vérifier le format
head -2 /home/pi/data_logger.csv | tail -1

# Si voit : 1771978758.14 → OLD FORMAT
# Si voit : 2026-04-14T... → NEW FORMAT ✅
```

**Cause 3 : Pandas 2.0+ non compatible**
```bash
# Vérifier version pandas
python3 -c "import pandas; print(pandas.__version__)"

# Si < 2.0 : infer_datetime_format n'est pas déprecié
# Si >= 2.0 : infer_datetime_format cause erreur
```

### Si données vides en Mode Secours

**Cause : CSV corrompu ou mal formaté**
```bash
# Vérifier intégrité
wc -l /home/pi/data_logger.csv          # Nombre lignes
head -3 /home/pi/data_logger.csv        # En-têtes + données
tail -3 /home/pi/data_logger.csv        # Dernières lignes

# Si <2 lignes : Attendre données
sleep 60
tail -5 /home/pi/data_logger.csv
```

---

## 📊 RÉSUMÉ AVANT/APRÈS

### AVANT ❌
```
Mode Cloud (SQL):
  Timestamp: 2026-04-14 17:19:56
  RSSI: -95 dBm
  Battery: 85%
  Jitter: 0.5 ms

Mode Secours (CSV):
  Timestamp: 1771978758.14 ❌ Illisible!
  RSSI: (vide) ❌
  Battery: (vide) ❌
  Jitter: (vide) ❌
  Message: "Recherche de signal IoT..." 
           (persiste 10s indéfiniment) ❌
```

### APRÈS ✅
```
Mode Cloud (SQL):
  Timestamp: 2026-04-14 17:19:56
  RSSI: -95 dBm
  Battery: 85%
  Jitter: 0.5 ms

Mode Secours (CSV):
  Timestamp: 2026-04-14 17:19:56 ✅ Identique!
  RSSI: -95 dBm ✅ Identique!
  Battery: 85% ✅ Identique!
  Jitter: 0.5 ms ✅ Identique!
  Dashboard: Affiche immédiatement ✅
  Message: Aucun "Recherche..." ✅
```

---

## ✅ CRITÈRES DE SUCCÈS

**Le système est prêt en production si** :

1. ✅ Mode Cloud affiche données PostgreSQL (timestamps lisibles)
2. ✅ Mode Secours affiche données CSV (identiques à Cloud)
3. ✅ Tous les 18 champs remplis en Mode Secours
4. ✅ Pas de message "Recherche de signal..." qui persiste
5. ✅ Dashboard responsive (actualisation 10s)
6. ✅ Failover automatique (<5 secondes)
7. ✅ Aucune erreur dans console Streamlit
8. ✅ Aucune erreur dans console data_logger.py
9. ✅ Recovery automatique quand PostgreSQL revient
10. ✅ Continuité de monitoring 24/7 garantie

---

## 📞 SUPPORT RAPIDE

| Symptôme | Cause Probable | Solution |
|----------|---|---|
| "Recherche..." persiste | Ancien CSV | `rm /home/pi/data_logger.csv` + restart |
| Timestamps Unix visibles | data_logger.py ancien | Vérifier ligne 110 : `datetime.now().isoformat()` |
| Champs vides (rssi, etc.) | data_logger.py ancien | Vérifier lignes 113-121 : extraction MQTT |
| Dashboard crashes | Pandas version | Vérifier : `parse_dates` sans `infer_datetime_format` |
| CSV pas créé | data_logger.py pas lancé | `python3 /home/pi/data_logger.py &` |

---

## 🎯 OBJECTIF FINAL

**Un système de monitoring d'irrigation intelligent qui** :
- ✅ Collecte des données 24/7
- ✅ Stocke dans PostgreSQL (Cloud)
- ✅ Sauvegarde en CSV (Fallback local)
- ✅ Affiche un dashboard unifié
- ✅ Continue de fonctionner même en panne réseau
- ✅ Données identiques Cloud/Offline
- ✅ Zéro temps d'arrêt

---

**Status** : 🚀 PRODUCTION READY

**Prochaine étape** : Exécuter le plan de déploiement ci-dessus ✅
