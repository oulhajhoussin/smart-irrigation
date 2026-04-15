# 🌍 Architecture Complète d'Irrigation Intelligente : Edge vs Fog Computing

Ce document synthétise l'architecture complète d'un système IoT défini par logiciel (Software-Defined IoT), intégrant l'acquisition radio, l'orchestration dynamique, la résilience réseau et l'intelligence artificielle embarquée (TinyML).

---

## 🛠️ Phase 1 : L'Architecture Matérielle et le Pipeline de Données
Structure la base de ton système de bout en bout, de la terre jusqu'au tableau de bord.

* **1. Déploie la Couche Capteur (Edge Devices) :**
  * Utilise tes nœuds Arduino pour lire l'humidité du sol.
  * Transmets ces données en continu via le protocole radio LoRa, assurant une communication longue portée sans dépendance à Internet.
* **2. Configure la Passerelle (Edge Gateway - ESP32 TTGO) :**
  * Réceptionne les trames LoRa.
  * Formate les données en JSON.
  * Agis comme un pont réseau : publie ces données sur le réseau WiFi local via le protocole MQTT.
  * Pilote physiquement les actionneurs (les relais de la pompe et des vannes).
* **3. Mets en place la Supervision (Fog Layer - Raspberry Pi) :**
  * Écoute le trafic MQTT en arrière-plan.
  * Enregistre les données brutes de manière robuste dans un fichier `donnees_capteurs.csv`.
  * Propulse l'interface graphique Streamlit pour une visualisation des métriques en temps réel.

---

## ⚖️ Phase 2 : Les Paradigmes de Prise de Décision
Analyse et implémente les deux scénarios fondamentaux de ton étude comparative.

* **Scénario 1 : Le Fog Computing (Décision Centralisée)**
  * **Logique :** Centralise l'intelligence sur le Raspberry Pi. Le script Python lit les données, applique un algorithme d'hystérésis (ex: seuils à 40% et 80%) et envoie l'ordre d'activation au TTGO via MQTT.
  * **Analyse :** Mets en avant la vision globale et la facilité de mise à jour centralisée. Souligne sa vulnérabilité majeure : le point de défaillance unique (SPOF) en cas de perte WiFi.
* **Scénario 2 : L'Edge Computing (Décision Décentralisée)**
  * **Logique :** Déporte l'intelligence directement sur le microcontrôleur TTGO. Dès réception de la trame LoRa, l'ESP32 évalue l'humidité et déclenche les relais localement.
  * **Analyse :** Démontre la latence ultra-faible et la résilience totale aux coupures réseau. Note la contrainte de la puissance de calcul limitée.

---

## 🛡️ Phase 3 : Orchestration Dynamique et Tolérance aux Pannes
Prouve la robustesse de ton système en le rendant adaptatif et tolérant aux pannes matérielles.

* **1. Intègre le Switch d'Orchestration :**
  * Ajoute un interrupteur sur ton interface Streamlit.
  * Publie un message sur le topic `irrigation/mode` pour basculer dynamiquement l'ensemble du système entre le mode "FOG" et "EDGE".
* **2. Code le "Fail-Safe" (Survie Automatique) :**
  * Programme le TTGO pour vérifier la santé de la connexion WiFi et MQTT.
  * En cas de perte du Raspberry Pi, force le TTGO à basculer automatiquement en mode EDGE pour sauver les cultures.
* **3. Implémente le Monitoring d'Urgence :**
  * En cas de panne réseau, configure le TTGO pour qu'il devienne son propre routeur (Mode Access Point).
  * Lance un mini-serveur Web interne générant une page HTML.
  * Connecte-toi avec un smartphone directement au TTGO pour vérifier l'état des vannes dans le champ.
  * Ajoute un délai d'expiration (Timeout) pour couper ce réseau de secours après 30 minutes et préserver la batterie.

---

## 🧠 Phase 4 : Intelligence Artificielle et Automatisation (MLOps)
Remplace les règles statiques par un système intelligent et auto-apprenant.

* **1. Embarque le TinyML sur le TTGO :**
  * Utilise ton dataset pour entraîner un modèle de classification (ex: Random Forest) sur ton PC ou le Pi.
  * Convertis ce modèle mathématique en code C++ (`.h`).
  * Fais croiser à l'IA l'humidité, la qualité du signal (RSSI) et la batterie pour prendre des décisions d'arrosage anticipées et nuancées au niveau Edge.
* **2. Déploie la Boucle MLOps :**
  * Automatise l'entraînement régulier du modèle sur le Raspberry Pi avec les nouvelles données collectées.
  * Mets à jour le "cerveau" du TTGO à distance et sans fil grâce à la technologie OTA (Over-The-Air).

---

## 🔋 Phase 5 : Optimisation Énergétique (Cycle de Vie)
Garantis la viabilité industrielle du projet.

* **Applique le Deep Sleep aux capteurs :**
  * Programme tes nœuds Arduino pour alterner entre quelques secondes d'activité (lecture + envoi LoRa) et plusieurs minutes de sommeil profond.
  * Démontre comment cette technique fait chuter la consommation de 40 mA à environ 20 µA, faisant passer l'autonomie des batteries de quelques jours à plusieurs années.