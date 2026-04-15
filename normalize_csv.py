import os
import csv

directory = r"c:\Users\GODFATHER\Desktop\dataset"
output_file = os.path.join(directory, "dataset_normalized.csv")

# Ensure we don't read the output file if it exists
csv_files = [f for f in os.listdir(directory) if f.endswith('.csv') and f != "dataset_normalized.csv"]

standard_columns = [
    "timestamp", "node_id", "counter", "soil_pct", "raw_data", "payload_bytes", 
    "rssi", "snr", "rtt_cloud_ms", "decision_latency_ms", "jitter_ms", 
    "missing_packets", "cpu_percent", "ram_percent", "node_batt_pct", 
    "node_current_ma", "gateway_batt_pct", "gateway_current_ma"
]

# Column mapping for inconsistencies
column_mapping = {
    # Variations in Group 4
    "Timestamp": "timestamp",
    "Node": "node_id",
    "RSSI": "rssi",
    "Raw_Data": "raw_data",
    "SNR": "snr",
    "Batt_Pct": "node_batt_pct",
    "Current_mA": "node_current_ma"
}

total_rows_processed = 0

print(f"Démarrage de la normalisation de {len(csv_files)} fichiers CSV...")

with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=standard_columns)
    writer.writeheader()
    
    for filename in csv_files:
        filepath = os.path.join(directory, filename)
        file_row_num = 0
        with open(filepath, 'r', newline='', encoding='utf-8-sig') as infile: # utf-8-sig to handle optional BOM
            reader = csv.DictReader(infile)
            for row in reader:
                new_row = {}
                for key, value in row.items():
                    if key is None:
                        continue
                    key_stripped = key.strip()
                    std_key = column_mapping.get(key_stripped, key_stripped)
                    # Keep data only if it maps to one of the standard columns
                    if std_key in standard_columns:
                        new_row[std_key] = value
                writer.writerow(new_row)
                file_row_num += 1
                total_rows_processed += 1
        print(f"Traité '{filename}' : {file_row_num} lignes.")

print(f"\nNormalisation terminée avec succès !")
print(f"Total des lignes fusionnées : {total_rows_processed}")
print(f"Fichier résultat généré : {output_file}")
