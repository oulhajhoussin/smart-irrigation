#include <SPI.h>
#include <LoRa.h>
#include <LowPower.h> // NOUVELLE BIBLIOTHÈQUE POUR LE SOMMEIL

// ==========================================
// A MODIFIER POUR CHAQUE ARDUINO :
#define NODE_ID "NODE1" // Remplacer par "NODE2" sur l'autre
// ==========================================

static const int LORA_CS   = 10;
static const int LORA_RST  = 9;
static const int LORA_DIO0 = 2;
static const long LORA_FREQ = 433E6;
  
static const int SOIL_PIN = A0;
uint32_t counter = 0;

int rawDry = 850;
int rawWet = 350;

int clampInt(int x, int a, int b) { 
  return (x < a) ? a : (x > b) ? b : x; 
}

int rawToPercent(int raw) {
  long pct = (long)(rawDry - raw) * 100L / (rawDry - rawWet);
  return clampInt((int)pct, 0, 100);
}

int nodeNumber = 1;

// NOUVEAU : Variable pour définir le temps de sommeil de base (en secondes)
// Pour les tests, on garde 8s et 11s. En production, on mettra plutôt 900s (15 min)
int baseSleepSeconds; 

void setup() {
  Serial.begin(115200);

  String nodeStr = String(NODE_ID);
  nodeNumber = nodeStr.substring(4).toInt();
  
  // Calcul du temps de sommeil de base selon le numéro du nœud
  baseSleepSeconds = 5 + (nodeNumber * 3); 

  randomSeed(analogRead(A1) + (nodeNumber * 1000) + millis());

  LoRa.setPins(LORA_CS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (true) delay(1000);
  }

  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.enableCrc();
  LoRa.setTxPower(17);

  Serial.print(NODE_ID);
  Serial.println(" Soil TX ready. Base Sleep: " + String(baseSleepSeconds) + "s");
}

// NOUVELLE FONCTION : Gestion du sommeil profond
void enterDeepSleep(int sleepTimeSeconds) {
  // 1. Mettre le module LoRa en mode sommeil (Crucial !)
  LoRa.sleep();
  
  Serial.print("Zzz... Dors pour ");
  Serial.print(sleepTimeSeconds);
  Serial.println("s");
  delay(50); // Laisse le temps au port série de finir d'écrire

  // L'Arduino Uno/Nano ne peut dormir que 8 secondes maximum par instruction.
  // On fait une boucle pour accumuler les périodes de 8s (et moins)
  int timeRemaining = sleepTimeSeconds;
  
  while (timeRemaining > 0) {
    if (timeRemaining >= 8) {
      LowPower.powerDown(SLEEP_8S, ADC_OFF, BOD_OFF);
      timeRemaining -= 8;
    } else if (timeRemaining >= 4) {
      LowPower.powerDown(SLEEP_4S, ADC_OFF, BOD_OFF);
      timeRemaining -= 4;
    } else if (timeRemaining >= 2) {
      LowPower.powerDown(SLEEP_2S, ADC_OFF, BOD_OFF);
      timeRemaining -= 2;
    } else {
      LowPower.powerDown(SLEEP_1S, ADC_OFF, BOD_OFF);
      timeRemaining -= 1;
    }
  }
}

void loop() {
  // On s'assure que le module LoRa est bien réveillé
  LoRa.idle(); 
  
  int raw = analogRead(SOIL_PIN);
  int pct = rawToPercent(raw);

  String msg = String(NODE_ID) + "," + String(counter++) + "," + String(raw) + "," + String(pct);
  Serial.println("TX: " + msg);

  LoRa.beginPacket();
  LoRa.print(msg);
  LoRa.endPacket();

  // Calcul du temps total de sommeil avec la gigue
  int randomJitter = random(0, 4); // 0 à 3 secondes de décalage
  int totalSleepSeconds = baseSleepSeconds + randomJitter;

  // Appel de notre fonction de sommeil au lieu de delay()
  enterDeepSleep(totalSleepSeconds);
}
