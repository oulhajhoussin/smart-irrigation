# 🎯 DÉPLOIEMENT - PostgreSQL + Streamlit Fix

## 📋 RÉSUMÉ DES CHANGEMENTS

**Problème** : Streamlit ne pouvait pas se connecter à PostgreSQL  
**Cause** : IP incorrecte (`192.168.100.97` au lieu de `localhost`)  
**Solution** : Corriger la config + ajouter vrai fallback CSV

---

## 📦 FICHIERS À DÉPLOYER

| Fichier | Type | Action |
|---------|------|--------|
| `app.py` | Modifié | Transférer au Raspberry Pi |
| `diagnose_postgres.py` | Nouveau | Transférer au Raspberry Pi |
| `deploy_streamlit.sh` | Script | Exécuter sur le Raspberry Pi |

---

## 🚀 DÉPLOIEMENT (Option 1 : Manuel)

### Étape 1 : Transférer les fichiers
```bash
# Sur votre PC (Windows/Mac/Linux)
cd c:\Users\GODFATHER\Desktop\dataset\codes

# Transférer app.py
scp app.py pi@192.168.100.66:/home/pi/

# Transférer diagnose_postgres.py
scp diagnose_postgres.py pi@192.168.100.66:/home/pi/
```

### Étape 2 : Vérifier la connexion PostgreSQL
```bash
# Sur le Raspberry Pi
ssh pi@192.168.100.66

# Exécuter le diagnostic
python3 /home/pi/diagnose_postgres.py
```

**Résultat attendu** :
```
✅ psycopg2 is installed
✅ Connected to PostgreSQL!
✅ Found tables: iot_smart_irrigation_raw (N rows)
✅ CSV file exists
```

### Étape 3 : Redémarrer Streamlit
```bash
# Tuer l'ancienne instance
pkill -f "streamlit run app.py"

# Relancer (avec message clair dans la sidebar)
streamlit run /home/pi/app.py
```

### Étape 4 : Vérifier dans le navigateur
Allez sur : `http://192.168.100.66:8502`

**Vous devez voir dans la sidebar** :
- 🟢 `Status: Cloud (SQL)` → PostgreSQL actif
- OU
- 🟡 `Status: Local (CSV) - Mode Secours 🛡️` → Fallback actif

---

## 🤖 DÉPLOIEMENT (Option 2 : Automatisé)

### Étape 1 : Copier le script de déploiement
```bash
# Sur le Raspberry Pi
wget https://your-path/deploy_streamlit.sh
chmod +x deploy_streamlit.sh

# Ou via SCP depuis votre PC
scp deploy_streamlit.sh pi@192.168.100.66:/home/pi/
```

### Étape 2 : Exécuter le script
```bash
# Sur le Raspberry Pi
cd /home/pi
./deploy_streamlit.sh
```

Le script fera automatiquement :
1. ✅ Vérifier que vous êtes sur le Raspberry Pi
2. ✅ Installer psycopg2 si manquant
3. ✅ Sauvegarder l'ancien app.py
4. ✅ Copier les nouveaux fichiers
5. ✅ Exécuter le diagnostic
6. ✅ Relancer Streamlit

---

## 🧪 TESTS DE VALIDATION

### Test 1 : PostgreSQL Actif (Mode normal)
```bash
# Sur le Raspberry Pi
python3 diagnose_postgres.py

# Résultat attendu
✅ Connected to PostgreSQL!
✅ Found tables: iot_smart_irrigation_raw
```

Ouvrir Streamlit → Sidebar doit afficher **"Cloud (SQL)"** 🟢

---

### Test 2 : PostgreSQL Offline (Mode secours)
```bash
# Arrêter Docker pour simuler une panne
docker compose down

# Lancer Streamlit (il bascule automatiquement)
streamlit run /home/pi/app.py
```

**Résultat attendu** :
- Sidebar affiche **"Local (CSV) - Mode Secours 🛡️"** 🟡
- Graphes continuent de fonctionner (données du CSV local)
- Message d'erreur PostgreSQL visible dans le diagnostic

```bash
# Redémarrer Docker
docker compose up -d

# Streamlit revient automatiquement au mode SQL 🟢
```

---

### Test 3 : Psycopg2 Manquant
```bash
# Installer à nouveau si nécessaire
pip3 install psycopg2-binary

# Relancer Streamlit
streamlit run /home/pi/app.py
```

---

## 🔍 DIAGNOSTIC & TROUBLESHOOTING

### Erreur : "Connection refused on localhost:5432"
```bash
# Vérifier que Docker tourne
docker compose ps

# Résultat attendu
CONTAINER ID   STATUS
...postgres... Up 
...kafka...    Up

# Si absent, redémarrer
docker compose down -v
docker compose up -d --build
```

### Erreur : "module 'psycopg2' has no attribute 'connect'"
```bash
# Réinstaller psycopg2
pip3 uninstall psycopg2-binary
pip3 install psycopg2-binary
```

### Erreur : "CSV file not found"
```bash
# S'assurer que data_logger.py tourne
ps aux | grep data_logger

# Si absent, relancer
python3 /home/pi/data_logger.py &
```

### Erreur : "No data in PostgreSQL"
```bash
# Vérifier que Kafka envoie des données
docker compose logs kafka-consumer | tail -20

# Vérifier les tables
docker exec -it projet-dataops-mlops-postgres-1 psql -U airflow -d airflow -c "SELECT COUNT(*) FROM iot_smart_irrigation_raw;"
```

---

## 📊 ARCHITECTURE APRÈS FIX

```
┌──────────────────────────────────────────────────┐
│  RASPBERRY PI - Streamlit Dashboard             │
├──────────────────────────────────────────────────┤
│                                                   │
│  app.py (v2.0)                                   │
│  ├─ Tente PostgreSQL (localhost:5432)            │
│  │  ├─ Succès → Mode "Cloud (SQL)" 🟢            │
│  │  └─ Échec → Fallback vers CSV                 │
│  │                                               │
│  ├─ CSV Fallback (/home/pi/data_logger.csv)     │
│  │  └─ Mode "Local (CSV) - Secours 🛡️"          │
│  │                                               │
│  └─ Diagnostic intégré (🔧 sidebar)             │
│     ├─ Status PostgreSQL                        │
│     ├─ Chemin CSV                               │
│     ├─ Psycopg2 installé ?                      │
│     └─ Dernière synchronisation                 │
│                                                   │
├──────────────────────────────────────────────────┤
│              Interface Utilisateur                │
├──────────────────────────────────────────────────┤
│  📊 Graphes Humidité + Pompe (Temps réel)       │
│  🧠 KPIs Intelligence Locale                    │
│  ⚡ Performance Latence (FOG vs EDGE)           │
│  📜 Historique des Trames                       │
│                                                   │
└──────────────────────────────────────────────────┘
         ↓
    ┌────────────────────────────────────┐
    │  Docker Stack (Optionnel)           │
    ├────────────────────────────────────┤
    │ PostgreSQL (localhost:5432)         │ ← app.py lit
    │ Kafka (pour data_logger.py)         │
    │ Grafana (dashboard temps réel)      │
    │ MLflow (tracking modèles)           │
    └────────────────────────────────────┘
```

---

## ✅ CHECKLIST DE DÉPLOIEMENT

- [ ] Fichiers `app.py` et `diagnose_postgres.py` transférés au Pi
- [ ] `python3 diagnose_postgres.py` exécuté avec succès
- [ ] Streamlit relancé : `streamlit run /home/pi/app.py`
- [ ] Sidebar affiche "Cloud (SQL)" ou "Local (CSV)"
- [ ] Graphes s'affichent sans erreur
- [ ] Test fallback : `docker compose down` puis vérifier le switch automatique
- [ ] Test récupération : `docker compose up -d` puis vérifier le retour au mode Cloud

---

## 📞 SUPPORT

Si vous rencontrez des erreurs :

1. **Exécuter le diagnostic** :
   ```bash
   python3 /home/pi/diagnose_postgres.py
   ```

2. **Vérifier les logs Streamlit** :
   ```bash
   streamlit run /home/pi/app.py --logger.level=debug
   ```

3. **Vérifier les logs Docker** :
   ```bash
   docker compose logs postgres --tail=30
   docker compose logs kafka --tail=30
   ```

4. **Consulter le fichier récapitulatif** :
   - `STREAMLIT_POSTGRESQL_FIX_SUMMARY.md`
   - `POSTGRESQL_FIX_GUIDE.md`

---

**Date du déploiement** : 14/04/2026  
**Version** : 2.0 (PostgreSQL + CSV Fallback)  
**Status** : ✅ Prêt pour production
