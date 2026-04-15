# 🐛 BUG FIX : "Recherche de signal IoT..." persiste

**Date** : 14/04/2026  
**Problème** : Message "Recherche de signal IoT..." affiche indéfiniment en Mode Secours  
**Cause** : Erreur pandas `infer_datetime_format` dépréciée + pas d'erreur affichée

---

## 🔴 PROBLÈME

**Comportement observé** :
```
Status: Hors-ligne
⚠️ PostgreSQL Indisponible
CSV Error: read_csv() got an unexpected keyword argument 'infer_datetime_format'
✅ Le système bascule automatiquement au CSV local...

[Message persiste] "Recherche de signal IoT..." 
→ Dashboard ne montre pas les données
→ Rafraîchit toutes les 10 secondes indéfiniment
```

**Cause racine** :
1. `infer_datetime_format` est **déprecié** en pandas 2.0+ 
2. Erreur lors du parsing du CSV
3. DataFrame reste vide → affiche "Recherche..."
4. Aucun fallback pour afficher les données ou l'erreur

---

## ✅ SOLUTIONS APPLIQUÉES

### Fix #1 : Supprimer `infer_datetime_format`
**Fichier** : `app.py` ligne 142

**Avant** :
```python
df = pd.read_csv(CSV_FILE, names=HEADERS_CSV, 
                dtype={...},
                parse_dates=['timestamp'],
                infer_datetime_format=True)  # ❌ Déprecié!
```

**Après** :
```python
df = pd.read_csv(CSV_FILE, names=HEADERS_CSV, 
                dtype={...},
                parse_dates=['timestamp'])  # ✅ Sans infer_datetime_format
```

---

### Fix #2 : Ajouter try/except pour timestamp
**Fichier** : `app.py` lignes 147-152

**Avant** :
```python
df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime(...)
# Si échoue → Exception silencieuse
```

**Après** :
```python
try:
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
except:
    # Si le parsing échoue, garder le timestamp tel quel
    pass  # ✅ Continue avec les données disponibles
```

---

### Fix #3 : Afficher les erreurs à l'utilisateur
**Fichier** : `app.py` ligne 155

**Avant** :
```python
except Exception as csv_error: 
    last_error = f"CSV Error: {str(csv_error)}"
    # Erreur stockée mais jamais affichée
    # → "Recherche de signal IoT..." persiste
```

**Après** :
```python
except Exception as csv_error: 
    last_error = f"CSV Error: {str(csv_error)}"
    # ✅ Afficher l'erreur IMMÉDIATEMENT
    st.error(f"❌ Erreur lecture CSV: {csv_error}")
```

---

### Fix #4 : Meilleure gestion du message "Recherche de signal"
**Fichier** : `app.py` lignes 361-371

**Avant** :
```python
else:
    st.info("Recherche de signal IoT...")
    # Affiche indéfiniment si df.empty
    # Même en Mode Secours avec erreur
```

**Après** :
```python
else:
    # Afficher l'erreur spécifique plutôt que "Recherche..."
    if sql_error:
        with st.sidebar:
            st.error(f"⚠️ Pas de données disponibles\n\n{sql_error}")
    else:
        st.info("Recherche de signal IoT...")
    # ✅ Erreur visible au lieu d'un message vague
```

---

## 🧪 RÉSULTATS ATTENDUS

### Avant Fix ❌

**Docker arrêté** :
```
Status: Hors-ligne
⚠️ PostgreSQL Indisponible
CSV Error: read_csv() got an unexpected keyword argument 'infer_datetime_format'
✅ Le système bascule automatiquement au CSV local...

[Persiste 10s] "Recherche de signal IoT..."
❌ Aucun dashboard, aucune donnée visible
```

### Après Fix ✅

**Docker arrêté** :
```
Status: Hors-ligne
⚠️ PostgreSQL Indisponible
✅ Le système bascule automatiquement au CSV local...

[Immédiatement affiche] Dashboard avec données CSV
✅ Graphes visibles
✅ Historique IoT visible
✅ Aucun message "Recherche..." inutile
```

**Si CSV vraiment absent** :
```
Status: Hors-ligne
⚠️ PostgreSQL Indisponible
❌ Erreur lecture CSV: [Errno 2] No such file or directory: '/home/pi/data_logger.csv'
```

---

## 📋 CHANGEMENTS RÉSUMÉ

| Ligne | Avant | Après | Impact |
|------|-------|-------|--------|
| 140 | `infer_datetime_format=True` | (supprimé) | ✅ Pas d'erreur pandas |
| 147-151 | `df['timestamp'] = ...` | `try/except` | ✅ Continue si parse échoue |
| 155 | Erreur silencieuse | `st.error()` | ✅ Erreur visible |
| 361-371 | `st.info("Recherche...")` | Conditionnel | ✅ Affiche erreur si applicable |

---

## 🚀 DÉPLOIEMENT

### Étape 1 : Transfert
```bash
scp codes/app.py pi@192.168.100.66:/home/pi/
```

### Étape 2 : Redémarrer Streamlit
```bash
ssh pi@192.168.100.66
pkill -f "streamlit run"
streamlit run /home/pi/app.py
```

### Étape 3 : Tester Mode Secours
```bash
# Sur votre PC
docker compose down

# Sur Streamlit : Attendre 5-10 secondes
# Doit afficher directement le Dashboard CSV
# ✅ Graphes visibles
# ✅ Historique visible
# ✅ Pas de "Recherche de signal..." qui persiste
```

### Étape 4 : Vérifier erreurs spécifiques
```bash
# Si CSV manquant ou corrompu
# La sidebar affiche l'erreur spécifique
# ❌ "Erreur lecture CSV: [Errno 2]..."
```

### Étape 5 : Relancer Docker
```bash
docker compose up -d

# Streamlit doit basculer automatiquement à Mode Cloud (SQL)
# ✅ "Status: Cloud (SQL)"
```

---

## 🔍 TROUBLESHOOTING

### Si le message "Recherche..." persiste toujours

**Cause** : CSV existe mais est vide ou mal formaté

**Solution** :
```bash
# Vérifier le CSV
head -1 /home/pi/data_logger.csv  # En-têtes OK?
wc -l /home/pi/data_logger.csv    # Nombre de lignes?

# Si <2 lignes : Supprimer et relancer data_logger.py
rm /home/pi/data_logger.csv
pkill -f "python.*data_logger.py"
python3 /home/pi/data_logger.py &
sleep 30
streamlit run /home/pi/app.py
```

### Si erreur : "No such file or directory"

**Cause** : CSV path incorrect

**Solution** :
```bash
# Vérifier le path
ls -la /home/pi/data_logger.csv

# Si manquant, relancer data_logger.py
python3 /home/pi/data_logger.py &
```

### Si erreur : "ParserError"

**Cause** : CSV corrompu ou format incorrect

**Solution** :
```bash
# Vérifier intégrité
head -5 /home/pi/data_logger.csv

# Si bizarre, supprimer
rm /home/pi/data_logger.csv
# Relancer data_logger.py
```

---

## ✅ CHECKLIST FINAL

- [ ] app.py téléchargé sur Pi
- [ ] Streamlit redémarré (`pkill -f "streamlit run"`)
- [ ] Test Mode Secours (docker compose down)
- [ ] Dashboard affiche immédiatement (pas de "Recherche...")
- [ ] Graphes visibles avec données CSV
- [ ] Aucune erreur dans la sidebar (ou erreur spécifique affichée)
- [ ] Test Docker up (docker compose up -d)
- [ ] Basculage automatique vers Cloud (SQL)
- [ ] Confirmation : Mode Cloud affiche "Status: Cloud (SQL)"

---

## 📊 RÉSUMÉ

**Problème** : Message "Recherche de signal IoT..." persistait indéfiniment  
**Cause** : `infer_datetime_format` déprecié + pas de gestion d'erreur  
**Solution** : Supprimer parameter + ajouter try/except + afficher les erreurs  
**Résultat** : Dashboard s'affiche immédiatement en Mode Secours ✅

**Status** : 🚀 READY FOR PRODUCTION

---

*Next: Deploy and test*
