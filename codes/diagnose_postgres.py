#!/usr/bin/env python3
"""
🔍 Diagnostic Script for PostgreSQL Connection
Run this on the Raspberry Pi to verify connectivity
"""

import sys
import os

print("=" * 60)
print("🔍 PostgreSQL DIAGNOSTIC TOOL")
print("=" * 60)

# 1. Check psycopg2
print("\n[1/5] Checking psycopg2 installation...")
try:
    import psycopg2
    print("✅ psycopg2 is installed")
except ImportError:
    print("❌ psycopg2 NOT installed!")
    print("   Fix: pip3 install psycopg2-binary")
    sys.exit(1)

# 2. Check database connectivity
print("\n[2/5] Testing PostgreSQL connection...")
try:
    conn = psycopg2.connect(
        host="localhost",
        database="airflow",
        user="airflow",
        password="airflow",
        port=5432,
        connect_timeout=3
    )
    print("✅ Connected to PostgreSQL!")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n   TROUBLESHOOTING:")
    print("   1. Check if Docker is running: docker ps")
    print("   2. Check Postgres logs: docker compose logs postgres")
    print("   3. Verify DB exists: docker exec <postgres_container> psql -U airflow -l")
    sys.exit(1)

# 3. Check database structure
print("\n[3/5] Checking database tables...")
try:
    conn = psycopg2.connect(
        host="localhost",
        database="airflow",
        user="airflow",
        password="airflow",
        port=5432
    )
    cur = conn.cursor()
    
    # List all tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = cur.fetchall()
    
    if tables:
        print("✅ Found tables in 'airflow' database:")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cur.fetchone()[0]
            print(f"   - {table[0]}: {count} rows")
    else:
        print("⚠️ No tables found in database (fresh install)")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Error checking tables: {e}")
    sys.exit(1)

# 4. Check if IoT table exists
print("\n[4/5] Checking for IoT Smart Irrigation table...")
try:
    conn = psycopg2.connect(
        host="localhost",
        database="airflow",
        user="airflow",
        password="airflow",
        port=5432
    )
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) FROM iot_smart_irrigation_raw LIMIT 1")
        count = cur.fetchone()[0]
        print(f"✅ iot_smart_irrigation_raw table exists ({count} rows)")
    except:
        print("⚠️ iot_smart_irrigation_raw table NOT found")
        print("   (This is OK if Kafka hasn't started sending data yet)")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")

# 5. Check CSV fallback
print("\n[5/5] Checking CSV fallback file...")
csv_path = "/home/pi/data_logger.csv"
if os.path.exists(csv_path):
    size = os.path.getsize(csv_path)
    print(f"✅ CSV file exists: {csv_path} ({size} bytes)")
else:
    print(f"⚠️ CSV file NOT found: {csv_path}")
    print("   (data_logger.py may not have created it yet)")

print("\n" + "=" * 60)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 60)
print("\nRECOMMENDATIONS:")
print("1. If PostgreSQL fails: docker compose up -d")
print("2. If table is empty: wait for Kafka to send data")
print("3. If CSV is missing: run data_logger.py first")
print("4. Run Streamlit: streamlit run app.py")
