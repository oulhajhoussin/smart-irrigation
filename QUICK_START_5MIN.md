# ⚡ QUICK START - 5 MINUTES POUR RESTAURER GRAFANA

**Vous êtes ici parce que**: Grafana affiche "No data" et vous voulez réparer rapidement.

---

## 🎯 LE PROBLÈME EN UNE PHRASE

CSV manquait 2 champs (`irrigation_status` + `rtt_cloud_ms`) → Database ne reçoit pas les données → Grafana affiche "No data"

---

## ✅ SOLUTION EN 3 ÉTAPES (5 MINUTES)

### Étape 1: Copier 2 fichiers (1 minute)
```powershell
# Ouvrir PowerShell et exécuter:
scp C:\Users\GODFATHER\Desktop\dataset\codes\data_logger_NEW.py pi@192.168.100.66:/home/pi/data_logger.py
scp C:\Users\GODFATHER\Desktop\dataset\codes\app_NEW.py pi@192.168.100.66:/home/pi/app.py
```

### Étape 2: Redémarrer services (2 minutes)
```powershell
# RPi redémarrage
ssh pi@192.168.100.66 "sudo systemctl restart iot_logger"

# Docker redémarrage
cd C:\Users\GODFATHER\Desktop\dataset\projet-dataops-mlops
docker compose restart data-consumer
```

### Étape 3: Vérifier (2 minutes)
```powershell
# Ouvrir Streamlit (doit afficher "Cloud (SQL) ✅")
start http://192.168.100.66:8501

# Ouvrir Grafana (doit afficher des données)
start http://192.168.100.97:3000
```

---

## 🎉 C'EST TOUT!

Si vous voyez:
- ✅ Streamlit: "Cloud (SQL) ✅"
- ✅ Grafana: Données visibles (pas "No data")
- ✅ Badge déclenchements: Nombre > 0

→ **Félicitations! Système restauré!** 🚀

---

## ❓ Si ça ne fonctionne pas

**Vérifier que les services ont redémarré**:
```powershell
# RPi
ssh pi@192.168.100.66 "systemctl is-active iot_logger"
# Doit afficher: active

# Docker
docker ps | grep data-consumer
# Doit montrer: data-consumer UP
```

**Si toujours problème**:
- Lire: `DEPLOYMENT_GUIDE.md` section "TROUBLESHOOTING"
- Lire: `DELIVERABLES.md` section "FAQ"

---

## 📚 Pour COMPRENDRE les changements

Voir: `COMPARISON_BEFORE_AFTER.md` (avant/après côte-à-côte)

---

## 📋 Pour DÉPLOIEMENT COMPLET

Voir: `DEPLOYMENT_GUIDE.md` (avec checklist complète)

---

**✅ Vous êtes prêt! Lancez les 3 commandes ci-dessus.**
