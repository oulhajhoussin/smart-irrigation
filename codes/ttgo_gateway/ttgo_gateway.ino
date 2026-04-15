#include <WiFi.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <axp20x.h>
#include <WebServer.h>
#include "tinyml_edge_brain.h"

Eloquent::ML::Port::RandomForest ai_edge;

const char* WIFI_SSID = "HUAWEI-2.4G-aPF5";
const char* WIFI_PASS = "ZwdM2UXJ";

const char* MQTT_HOST = "192.168.100.66";
const int   MQTT_PORT = 1883;

WiFiClient espClient;
PubSubClient mqtt(espClient);

#define LORA_SCK  5
#define LORA_MISO 19
#define LORA_MOSI 27
#define LORA_CS   18
#define LORA_RST  14
#define LORA_IRQ  26
#define LORA_FREQ 433E6

const int PUMP_PIN   = 25; 
const int VALVE1_PIN = 13; 
const int VALVE2_PIN = 4;  

bool isNode1Watering = false;
bool isNode2Watering = false;

// --- SONDAGE DE TESTS (CHRONOMÉTRIE) ---
unsigned long last_tx_time_node1 = 0;
unsigned long last_tx_time_node2 = 0;
float last_latency_ms = 0.0; // NOUVEAU: Mémorisation globale pour le dashboard

AXP20X_Class axp;

// ==========================================
// --- VARIABLES D'ORCHESTRATION ET SURVIE ---
// ==========================================
String operating_mode = "FOG"; 
WebServer server(80);          
bool ap_active = false;        
unsigned long last_ap_time = 0;
const unsigned long AP_TIMEOUT = 30 * 60 * 1000; 

int last_hum_node1 = 0; 
int last_hum_node2 = 0;

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Tableau de Bord EDGE</title>";
  html += "<style>body{font-family:Arial; background:#1e1e1e; color:white; text-align:center;} .card{background:#333; padding:20px; margin:10px; border-radius:10px;}</style></head><body>";
  html += "<h2 style='color:#ff4b4b;'>🚨 MODE DE SURVIE : " + operating_mode + "</h2>";
  if(ap_active) html += "<p>Réseau principal hors ligne. Contrôle autonome actif.</p>";

  html += "<div class='card'><h3>Zone A (Node 1)</h3>";
  html += "<p>Humidité : " + String(last_hum_node1) + "%</p>";
  html += "<p>Vanne : " + String(isNode1Watering ? "<span style='color:green;'>OUVERTE</span>" : "<span style='color:red;'>FERMÉE</span>") + "</p></div>";

  html += "<div class='card'><h3>Zone B (Node 2)</h3>";
  html += "<p>Humidité : " + String(last_hum_node2) + "%</p>";
  html += "<p>Vanne : " + String(isNode2Watering ? "<span style='color:green;'>OUVERTE</span>" : "<span style='color:red;'>FERMÉE</span>") + "</p></div>";

  html += "</body></html>";
  server.send(200, "text/html", html);
}

void wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi OK: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n❌ WiFi indisponible ! Démarrage hors-ligne autorisé.");
  }
}

void updatePumpState() {
  if (isNode1Watering || isNode2Watering) {
    digitalWrite(PUMP_PIN, LOW); 
  } else {
    digitalWrite(PUMP_PIN, HIGH);
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  if (String(topic) == "irrigation/mode") {
    operating_mode = message;
    Serial.println("\n🔄 BASCULEMENT D'ARCHITECTURE : Le système passe en mode " + operating_mode);
    return;
  }
  
  if (String(topic) == "irrigation/control") {
    if (operating_mode == "EDGE") {
      Serial.println("⚠️ Ordre Fog ignoré : Le TTGO est en mode EDGE autonome.");
      return;
    }
    
    Serial.printf("📥 Ordre Fog reçu : %s\n", message.c_str());
    
    if (message == "NODE1_ON") {
      unsigned long rtt = millis() - last_tx_time_node1;
      last_latency_ms = (float)rtt; // MISE A JOUR MQTT
      Serial.printf("⏱️ [TEST LATENCE] FOG RTT (Node1) : %lu ms\n", rtt);
      digitalWrite(VALVE1_PIN, LOW);
      isNode1Watering = true;
    } else if (message == "NODE1_OFF") {
      unsigned long rtt = millis() - last_tx_time_node1;
      last_latency_ms = (float)rtt; // MISE A JOUR MQTT
      Serial.printf("⏱️ [TEST LATENCE] FOG RTT (Node1) : %lu ms\n", rtt);
      digitalWrite(VALVE1_PIN, HIGH);
      isNode1Watering = false;
    } else if (message == "NODE2_ON") {
      unsigned long rtt = millis() - last_tx_time_node2;
      last_latency_ms = (float)rtt; // MISE A JOUR MQTT
      Serial.printf("⏱️ [TEST LATENCE] FOG RTT (Node2) : %lu ms\n", rtt);
      digitalWrite(VALVE2_PIN, LOW);
      isNode2Watering = true;
    } else if (message == "NODE2_OFF") {
      unsigned long rtt = millis() - last_tx_time_node2;
      last_latency_ms = (float)rtt; // MISE A JOUR MQTT
      Serial.printf("⏱️ [TEST LATENCE] FOG RTT (Node2) : %lu ms\n", rtt);
      digitalWrite(VALVE2_PIN, HIGH);
      isNode2Watering = false;
    }
    updatePumpState();
  }
}

void mqttConnect() {
  if (WiFi.status() != WL_CONNECTED) return; 

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(callback); 
  
  if (!mqtt.connected()) {
    String clientId = "TBEAM-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqtt.connect(clientId.c_str())) {
      mqtt.subscribe("irrigation/control");
      mqtt.subscribe("irrigation/mode"); 
      Serial.println("✅ Connecté MQTT + Abonné aux topics control & mode");
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1200);

  pinMode(PUMP_PIN, OUTPUT);
  pinMode(VALVE1_PIN, OUTPUT);
  pinMode(VALVE2_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, HIGH);
  digitalWrite(VALVE1_PIN, HIGH);
  digitalWrite(VALVE2_PIN, HIGH);

  Wire.begin(21, 22); 
  if (axp.begin(Wire, AXP192_SLAVE_ADDRESS)) {
    axp.adc1Enable(AXP202_BATT_VOL_ADC1 | AXP202_BATT_CUR_ADC1, true);
  }

  wifiConnect();
  mqttConnect();

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_CS);
  LoRa.setPins(LORA_CS, LORA_RST, LORA_IRQ);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init FAILED!");
    while (true) delay(1000);
  }

  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.enableCrc();
  Serial.println("LoRa init OK. En écoute...");
}

void loop() {
  bool isNetworkHealthy = (WiFi.status() == WL_CONNECTED) && mqtt.connected();
  static unsigned long lastReconnectAttempt = 0;

  if (!isNetworkHealthy) {
    if (operating_mode != "EDGE") {
      operating_mode = "EDGE";
      Serial.println("\n🚨 ALARME : Réseau perdu. Mode EDGE autonome activé de force !");
    }

    if (!ap_active) {
      WiFi.mode(WIFI_AP_STA); 
      WiFi.softAP("URGENCE-IRRIGATION", "12345678"); 
      server.on("/", handleRoot);
      server.begin();
      ap_active = true;
      last_ap_time = millis();
      Serial.println("📡 Réseau de secours créé. Connectez votre téléphone à 'URGENCE-IRRIGATION'");
    }

    if (millis() - lastReconnectAttempt > 10000) {
      lastReconnectAttempt = millis();
      if (WiFi.status() != WL_CONNECTED) WiFi.begin(WIFI_SSID, WIFI_PASS);
      else mqttConnect();
    }
  } else {
    mqtt.loop(); 
  }

  if (ap_active) {
    server.handleClient();
    if (millis() - last_ap_time > AP_TIMEOUT) {
      WiFi.softAPdisconnect(true);
      WiFi.mode(WIFI_STA);
      ap_active = false;
      Serial.println("💤 Timeout AP (30 min) : WiFi de secours désactivé pour sauver la batterie.");
    }
  }

  int packetSize = LoRa.parsePacket();
  if (!packetSize) return;

  String msg;
  while (LoRa.available()) msg += (char)LoRa.read();
  
  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();

  String nodeId = "unknown";
  int commaIndex = msg.indexOf(',');
  if (commaIndex > 0) {
    nodeId = msg.substring(0, commaIndex);
    nodeId.toLowerCase(); 
  }

  if (nodeId != "node1" && nodeId != "node2") return;

  int lastCommaIndex = msg.lastIndexOf(',');
  int humidity_pct = 50; 
  if (lastCommaIndex > 0) {
    humidity_pct = msg.substring(lastCommaIndex + 1).toInt();
  }

  // --- CALCUL DE L'INERTIE (Dérivée temporelle pour l'A.I.) ---
  float current_soil_pct_diff = 0.0;
  if (nodeId == "node1") {
    if (last_hum_node1 != 0) current_soil_pct_diff = (float)(humidity_pct - last_hum_node1);
    last_hum_node1 = humidity_pct;
  }
  if (nodeId == "node2") {
    if (last_hum_node2 != 0) current_soil_pct_diff = (float)(humidity_pct - last_hum_node2);
    last_hum_node2 = humidity_pct;
  }

  if (operating_mode == "EDGE") {
    unsigned long edge_start = micros(); 
    
    // --- NOUVEAU: INJECTION DE L'A.I. TINYML ---
    float features[2] = {(float)humidity_pct, current_soil_pct_diff};
    int ai_decision = ai_edge.predict(features);
    // ai_decision: 1 = ARROSER, 0 = COUPER
    
    if (ai_decision == 1) {
      if (nodeId == "node1" && !isNode1Watering) {
        digitalWrite(VALVE1_PIN, LOW);
        isNode1Watering = true;
        unsigned long edge_time = micros() - edge_start; 
        last_latency_ms = (float)edge_time / 1000.0; // MISE A JOUR MQTT
        Serial.printf("🤖 [EDGE AI] Décision LOCALE : Vanne 1 OUVERTE (⏱️ Latence : %lu µs)\n", edge_time);
      } else if (nodeId == "node2" && !isNode2Watering) {
        digitalWrite(VALVE2_PIN, LOW);
        isNode2Watering = true;
        unsigned long edge_time = micros() - edge_start;
        last_latency_ms = (float)edge_time / 1000.0; // MISE A JOUR MQTT
        Serial.printf("🤖 [EDGE AI] Décision LOCALE : Vanne 2 OUVERTE (⏱️ Latence : %lu µs)\n", edge_time);
      }
      updatePumpState();
    } 
    else {
      if (nodeId == "node1" && isNode1Watering) {
        digitalWrite(VALVE1_PIN, HIGH);
        isNode1Watering = false;
        unsigned long edge_time = micros() - edge_start;
        last_latency_ms = (float)edge_time / 1000.0; // MISE A JOUR MQTT
        Serial.printf("🤖 [EDGE AI] Décision LOCALE : Vanne 1 FERMÉE (⏱️ Latence : %lu µs)\n", edge_time);
      } else if (nodeId == "node2" && isNode2Watering) {
        digitalWrite(VALVE2_PIN, HIGH);
        isNode2Watering = false;
        unsigned long edge_time = micros() - edge_start;
        last_latency_ms = (float)edge_time / 1000.0; // MISE A JOUR MQTT
        Serial.printf("🤖 [EDGE AI] Décision LOCALE : Vanne 2 FERMÉE (⏱️ Latence : %lu µs)\n", edge_time);
      }
      updatePumpState();
    }
  }

  // ==========================================
  // 3. ENVOI DES DONNÉES AU RASPBERRY PI
  // ==========================================
  float battVoltage_mV = axp.getBattVoltage();          
  float battCurrent_mA = axp.getBattDischargeCurrent(); 
  int battPercent = map(battVoltage_mV, 3200, 4200, 0, 100);
  battPercent = constrain(battPercent, 0, 100);

  Serial.printf("✅ RX: %s | RSSI=%d | Mode: %s\n", msg.c_str(), rssi, operating_mode.c_str());
  
  String topic = "irrigation/soil/" + nodeId;
  String json = "{";
  json += "\"raw\":\"" + msg + "\",";
  json += "\"rssi\":" + String(rssi) + ",";
  json += "\"snr\":" + String(snr, 2) + ",";
  json += "\"gateway_batt_pct\":" + String(battPercent) + ",";
  json += "\"gateway_current_ma\":" + String(battCurrent_mA, 2) + ",";
  json += "\"decision_latency_ms\":" + String(last_latency_ms, 3); // NOUVEAU: Ajout de la latence au MQTT !
  json += "}";

  if (isNetworkHealthy) {
    if (nodeId == "node1") last_tx_time_node1 = millis(); 
    if (nodeId == "node2") last_tx_time_node2 = millis(); 
    mqtt.publish(topic.c_str(), json.c_str());
  }
}
