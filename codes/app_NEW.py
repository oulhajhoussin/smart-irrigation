#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📱 STREAMLIT DASHBOARD - Smart Irrigation System
==================================================
Tableau de bord temps réel pour supervision FOG/Cloud

Dual Mode:
  1. Cloud Mode (PRIORITÉ): PostgreSQL sur Docker (192.168.100.97:5432)
  2. CSV Fallback Mode: Local /home/pi/data_logger.csv (Mode Secours)

MODIFICATIONS:
✅ FIX #1: Lecture de 'irrigation_status' depuis DB (au lieu de raw_data)
✅ FIX #2: Support des 19 colonnes CSV (avec irrigation_status)
✅ FIX #3: Affichage unifié Pompe ON/OFF via irrigation_status
✅ FIX #4: Gestion robuste du RTT (rtt_cloud_ms n'est plus vide)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import numpy as np
import paho.mqtt.publish as publish
from datetime import datetime, timedelta

try:
    import psycopg2
except ImportError:
    psycopg2 = None

# ==========================================
# CONFIG PAGE
# ==========================================
st.set_page_config(
    page_title="Smart Irrigation — Enterprise Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# STYLE CSS (GRAFANA PREMIUM)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@400;600&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        background-color: #0B0E14; 
        color: #E1E1E1; 
    }
    .main { background-color: #0B0E14; }

    /* Banniere Irrigation Active (Bleu Grafana) */
    .banner-on {
        background: linear-gradient(94deg, #4B9BFF 0%, #154AA5 100%);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        color: white;
        font-weight: 700;
        font-size: 2rem;
        box-shadow: 0 4px 15px rgba(21, 74, 165, 0.4);
        margin-bottom: 15px;
        display: flex; 
        align-items: center; 
        justify-content: center;
        gap: 15px;
    }

    /* Banniere Arret (Rouge Grafana) */
    .banner-off {
        background: linear-gradient(94deg, #FF4B4B 0%, #B91C1C 100%);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        color: white;
        font-weight: 700;
        font-size: 2rem;
        box-shadow: 0 4px 15px rgba(185, 28, 28, 0.4);
        margin-bottom: 15px;
        display: flex; 
        align-items: center; 
        justify-content: center;
        gap: 15px;
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 1rem;
    }

    .section-header {
        font-size: 0.9rem;
        font-weight: 600;
        color: #808495;
        margin-bottom: 15px;
        border-left: 3px solid #4B9BFF;
        padding-left: 10px;
    }

    .cycle-counter {
        background: linear-gradient(135deg, #FFBB33 0%, #FF8800 100%);
        color: #0B0E14;
        border-radius: 10px;
        padding: 40px;
        text-align: center;
        font-size: 4rem;
        font-weight: 800;
        box-shadow: 0 8px 25px rgba(255, 136, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE CONFIG
# ==========================================
DB_CONFIG = {
    "host": "192.168.100.97",      # Docker sur PC local
    "database": "airflow",
    "user": "airflow",
    "password": "airflow",
    "port": 5432,
    "connect_timeout": 3
}

CSV_FILE = "/home/pi/data_logger.csv" if os.path.exists("/home/pi/data_logger.csv") else "data_logger.csv"

# ✅ FIX #2: En-têtes CSV mises à jour (19 colonnes avec irrigation_status)
HEADERS_CSV = [
    'timestamp', 'node_id', 'counter', 'soil_pct', 'irrigation_status',
    'raw_data', 'payload_bytes', 'rssi', 'snr', 'rtt_cloud_ms',
    'decision_latency_ms', 'jitter_ms', 'missing_packets', 'cpu_percent',
    'ram_percent', 'node_batt_pct', 'node_current_ma', 'gateway_batt_pct',
    'gateway_current_ma'
]

# ==========================================
# DATA FETCHING
# ==========================================
@st.cache_data(ttl=1)
def fetch_realtime_data():
    """
    Récupère les données temps réel
    
    Priorité:
      1. PostgreSQL (Cloud) - TABLE UNIFIÉE iot_smart_irrigation_raw
      2. CSV Local (Fallback) - /home/pi/data_logger.csv
    
    Retour:
      (df, status_dict, error_msg, total_pump_cycles)
    """
    df = pd.DataFrame()
    last_error = ""
    status = {"mode": "Hors-ligne", "pulse": "offline"}
    total_db_cycles = 0
    
    # ========================================
    # 1. TENTATIVE POSTGRESQL (PRIORITE)
    # ========================================
    if psycopg2:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            
            # ✅ FIX #1: Lire directement 'irrigation_status' de la DB (pas raw_data)
            try:
                df = pd.read_sql(
                    "SELECT * FROM iot_smart_irrigation_raw ORDER BY timestamp DESC LIMIT 2000",
                    conn
                )
            except:
                # Fallback ancienne table si elle n'existe pas
                df = pd.read_sql(
                    "SELECT * FROM raw_soil_moisture ORDER BY timestamp DESC LIMIT 2000",
                    conn
                )
            
            # Requête 2: Comptage réel des cycles de pompage
            cur = conn.cursor()
            try:
                # ✅ FIX #1: Compter via 'irrigation_status' (colonne dédiée)
                cur.execute("SELECT COUNT(*) FROM iot_smart_irrigation_raw WHERE irrigation_status = 1")
            except:
                # Fallback si colonne n'existe pas
                cur.execute("SELECT SUM(CASE WHEN raw_data LIKE '%ON%' THEN 1 ELSE 0 END) FROM iot_smart_irrigation_raw")
            
            total_db_cycles = cur.fetchone()[0] or 0
            cur.close()
            conn.close()
            
            if not df.empty:
                status = {"mode": "Cloud (SQL) ✅", "pulse": "online"}
                # Renommer pour affichage unifié
                if 'humidity' in df.columns:
                    df.rename(columns={'humidity': 'soil_pct'}, inplace=True)
        
        except Exception as e:
            last_error = f"SQL Error: {str(e)} | Bascule mode CSV..."
    
    # ========================================
    # 2. FALLBACK CSV (MODE SECOURS)
    # ========================================
    if df.empty and os.path.exists(CSV_FILE):
        try:
            # ✅ FIX #2: Parser 19 colonnes (avec irrigation_status)
            df = pd.read_csv(
                CSV_FILE,
                names=HEADERS_CSV,
                dtype={'raw_data': str, 'node_id': str},
                parse_dates=['timestamp']
            ).tail(1000)  # Derniers 1000 enregistrements
            
            # Format timestamps
            if not df.empty and 'timestamp' in df.columns:
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            status = {"mode": "Local (CSV) 🛡️ - Mode Secours", "pulse": "online"}
            
            # ✅ FIX #3: Compter via 'irrigation_status' (colonne #5 du CSV)
            if 'irrigation_status' in df.columns:
                total_db_cycles = (df['irrigation_status'] == 1).sum()
            else:
                # Fallback si colonne manquante
                total_db_cycles = df['raw_data'].apply(lambda x: 1 if 'ON' in str(x) else 0).sum()
        
        except Exception as csv_error:
            last_error = f"CSV Error: {str(csv_error)}"
            st.error(f"❌ Erreur lecture CSV: {csv_error}")
    
    # ========================================
    # 3. NORMALIZATION (SQL vs CSV)
    # ========================================
    if not df.empty:
        # Renommer colonnes
        if 'humidity' in df.columns:
            df.rename(columns={'humidity': 'soil_pct'}, inplace=True)
        if 'node_id' not in df.columns and 'node' in df.columns:
            df.rename(columns={'node': 'node_id'}, inplace=True)
        
        # Parser timestamps
        if 'timestamp' in df.columns:
            if pd.api.types.is_numeric_dtype(df['timestamp']):
                df['ts'] = pd.to_datetime(pd.to_numeric(df['timestamp'], errors='coerce'), unit='s')
            else:
                df['ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        # Colonnes dérivées
        df['node'] = df['node_id'].astype(str).str.lower().str.strip()
        
        # Soil pct
        h_col = 'soil_pct' if 'soil_pct' in df.columns else (df.columns[2] if len(df.columns) > 2 else df.columns[0])
        df['h'] = pd.to_numeric(df[h_col], errors='coerce').ffill().fillna(50)
        
        # ✅ FIX #3: Utiliser 'irrigation_status' directement (pas raw_data)
        if 'irrigation_status' in df.columns:
            df['pump'] = pd.to_numeric(df['irrigation_status'], errors='coerce').fillna(0)
        else:
            # Fallback si colonne manquante
            df['pump'] = df['raw_data'].apply(lambda x: 1 if 'ON' in str(x) else 0) if 'raw_data' in df.columns else 0
        
        # Colonnes numériques
        for col in ['rssi', 'snr', 'decision_latency_ms', 'gateway_batt_pct', 'rtt_cloud_ms']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').ffill().fillna(0)
    
    return df, status, last_error, total_db_cycles

# ==========================================
# MAIN RENDER
# ==========================================
df, status, sql_error, real_total = fetch_realtime_data()

# Menu HAMBURGER (Sidebar)
with st.sidebar:
    st.markdown(f"### Status: **{status['mode']}**")
    
    if sql_error:
        st.error(f"⚠️ **PostgreSQL Indisponible**\n\n{sql_error}")
        st.info("✅ Le système bascule automatiquement au CSV local pour la continuité du monitoring.")
    else:
        st.success("✅ Connecté à PostgreSQL (Cloud)")
    
    st.markdown("---")
    st.markdown("#### Contrôle Architecture")
    arch = st.radio("Mode :", ["Mode FOG", "Mode EDGE"])
    if st.button("Appliquer Configuration", use_container_width=True):
        try:
            publish.single(
                "irrigation/mode",
                "FOG" if "FOG" in arch else "EDGE",
                hostname="127.0.0.1"
            )
            st.toast("✅ Configuration envoyée au TTGO!")
        except Exception as mqtt_err:
            st.error(f"❌ Erreur MQTT: {mqtt_err}")
    
    st.write("---")
    st.caption(f"Dernière Sync: {time.strftime('%H:%M:%S')}")
    
    # Debug Info
    with st.expander("🔧 Informations Diagnostic"):
        st.code(f"""
MODE: {status['mode']}
POSTGRESQL: localhost:5432
DATABASE: airflow
CSV FALLBACK: {CSV_FILE}
CSV EXISTS: {os.path.exists(CSV_FILE)}
PSYCOPG2: {'✅ Installé' if psycopg2 else '❌ Non installé'}
COLONNES CSV: {len(HEADERS_CSV)} (irrigation_status inclus)
        """, language="text")

# ==========================================
# AFFICHAGE PRINCIPAL
# ==========================================
if not df.empty:
    st.markdown("### 🌾 Smart Irrigation - FOG Computing Dashboard (Raspberry Pi)")
    
    # ========================================
    # GRAPHIQUE FUSION: HUMIDITÉ + POMPE
    # ========================================
    from plotly.subplots import make_subplots
    
    # Préparation données
    df_pivot_h = df.pivot_table(index='ts', columns='node', values='h').ffill().fillna(50)
    # La pompe est partagée: on prend le max (si l'une des zones veut l'eau, pompe active)
    df_pump_single = df.groupby('ts')['pump'].max().ffill().fillna(0)
    
    f_combined = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 1. Courbes Humidité (Axe primaire)
    for node in df_pivot_h.columns:
        color = "#00FF7F" if 'node1' in str(node) else "#FFBB33"
        f_combined.add_trace(
            go.Scatter(
                x=df_pivot_h.index,
                y=df_pivot_h[node],
                name=f"Hums {node}",
                line=dict(color=color, width=2)
            ),
            secondary_y=False,
        )
    
    # 2. Zone Pompage (Axe secondaire)
    f_combined.add_trace(
        go.Scatter(
            x=df_pump_single.index,
            y=df_pump_single,
            name="État Pompe",
            fill='tozeroy',
            line=dict(color='rgba(0,0,0,0)'),
            mode='none',
            fillcolor="rgba(75, 155, 255, 0.25)"
        ),
        secondary_y=True,
    )
    
    f_combined.update_layout(
        title="Supervision IA : Humidité (N1/N2) & État Pompe Unique",
        template="plotly_dark",
        height=400,
        margin=dict(l=0, r=0, b=0, t=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    f_combined.update_yaxes(title_text="Humidité (%)", range=[0, 105], secondary_y=False)
    f_combined.update_yaxes(title_text="Pompe (0/1)", range=[0, 4], secondary_y=True, showgrid=False, visible=False)
    
    st.plotly_chart(f_combined, use_container_width=True)
    
    # ========================================
    # SECTION: DÉCISION & ACTIVITÉ
    # ========================================
    st.markdown('<div class="section-header">🧠 Intelligence Locale & Activité des Pompes</div>', unsafe_allow_html=True)
    c_g1, c_g2, c_stat, c_count = st.columns([5, 5, 8, 6])
    
    # Pré-calculs Node 1 & 2
    d1 = df[df['node'] == 'node1']
    d2 = df[df['node'] == 'node2']
    
    h1 = d1['h'].iloc[-1] if not d1.empty else 0
    h2 = d2['h'].iloc[-1] if not d2.empty else 0
    
    # ✅ FIX #3: Utiliser 'pump' (qui vient de irrigation_status)
    p1 = int(d1['pump'].iloc[-1]) if not d1.empty else 0
    p2 = int(d2['pump'].iloc[-1]) if not d2.empty else 0
    
    with c_g1:
        st.markdown('<div style="font-size:0.6rem; color:#808495; text-align:center;">HUMIDITÉ NODE 1</div>', unsafe_allow_html=True)
        f1 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=h1,
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#4B9BFF"}},
        ))
        f1.update_layout(height=180, margin=dict(l=20, r=20, b=10, t=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(f1, use_container_width=True)
    
    with c_g2:
        st.markdown('<div style="font-size:0.6rem; color:#808495; text-align:center;">HUMIDITÉ NODE 2</div>', unsafe_allow_html=True)
        f2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=h2,
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#FFBB33"}},
        ))
        f2.update_layout(height=180, margin=dict(l=20, r=20, b=10, t=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(f2, use_container_width=True)
    
    with c_stat:
        # Bannières
        b1_style = "banner-on" if p1 else "banner-off"
        b2_style = "banner-on" if p2 else "banner-off"
        st.markdown(f'<div class="{b1_style}" style="font-size:1rem; padding:12px; margin-bottom:10px;">ZONE A: {"🌊 IRRIGATION" if p1 else "🛑 COUPÉ"}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="{b2_style}" style="font-size:1rem; padding:12px; margin-bottom:0;">ZONE B: {"🌊 IRRIGATION" if p2 else "🛑 COUPÉ"}</div>', unsafe_allow_html=True)
    
    with c_count:
        st.markdown(f'<div class="cycle-counter" style="padding:15px; font-size:2.5rem; height:120px; display:flex; align-items:center; justify-content:center;">{int(real_total)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.6rem; color:#808495; text-align:center; margin-top:5px;">DÉCLENCHEMENTS POMPES (TOTAL)</div>', unsafe_allow_html=True)
    
    st.write("---")
    
    # ========================================
    # SECTION: PERFORMANCE & RÉSEAU
    # ========================================
    st.markdown('<div class="section-header">⚡ Performance Edge vs Fog — Latence & Réseau</div>', unsafe_allow_html=True)
    cp1, cp2, cp3 = st.columns([10, 6, 6])
    
    with cp1:
        f_lat = px.line(
            df,
            x='ts',
            y='decision_latency_ms',
            title="Latence de Décision IA",
            height=280,
            template="plotly_dark"
        )
        f_lat.update_layout(
            margin=dict(l=0, r=0, b=0, t=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(f_lat, use_container_width=True)
    
    with cp2:
        avg_l = df['decision_latency_ms'].mean()
        rssi_v = df['rssi'].iloc[-1]
        st.markdown(f"""
            <div class="glass-card" style="height:120px; padding:10px; margin-bottom:10px;">
                <p class="section-header" style="font-size:0.65rem; margin-bottom:5px;">Latence Moyenne (ms)</p>
                <h2 style="color:#00FF7F; text-align:center; margin:0;">{avg_l:.2f} ms</h2>
            </div>
            <div class="glass-card" style="height:120px; padding:10px; margin-bottom:0;">
                <p class="section-header" style="font-size:0.65rem; margin-bottom:5px;">Force Signal LoRa</p>
                <h2 style="text-align:center; margin:0;">{rssi_v} <span style="font-size:0.8rem;">dBm</span></h2>
            </div>
        """, unsafe_allow_html=True)
    
    with cp3:
        batt_v = df['gateway_batt_pct'].iloc[-1]
        fb = go.Figure(go.Indicator(
            mode="gauge+number",
            value=batt_v,
            number={'suffix': "%", 'font': {'size': 40, 'color': "white"}},
            title={'text': "Batterie ESP", 'font': {'size': 14, 'color': "#808495"}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#4B9BFF"},
                'bar': {'color': "#00FF7F" if batt_v > 20 else "#FF4B4B"},
                'bgcolor': "rgba(255,255,255,0.05)",
                'borderwidth': 2,
                'bordercolor': "rgba(255,255,255,0.1)",
                'steps': [
                    {'range': [0, 20], 'color': 'rgba(255, 75, 75, 0.2)'},
                    {'range': [20, 100], 'color': 'rgba(0, 255, 127, 0.1)'}
                ],
            }
        ))
        fb.update_layout(height=250, margin=dict(l=30, r=30, b=0, t=50), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fb, use_container_width=True)
    
    # ========================================
    # SECTION: HISTORIQUE TEMPS RÉEL
    # ========================================
    st.markdown('<div class="section-header">📜 Historique des Trames IoT (Temps Réel)</div>', unsafe_allow_html=True)
    logs = df[['ts', 'node', 'h', 'pump', 'decision_latency_ms', 'rssi']].tail(10).sort_values('ts', ascending=False)
    st.dataframe(logs, hide_index=True, use_container_width=True)

else:
    # Pas de données disponibles
    if sql_error:
        with st.sidebar:
            st.error(f"⚠️ Pas de données disponibles\n\n{sql_error}")
    else:
        st.info("🔍 Recherche de signal IoT...")

# ==========================================
# AUTO-REFRESH
# ==========================================
time.sleep(5)
st.rerun()
