#!/bin/bash
# 🚀 DEPLOYMENT SCRIPT FOR STREAMLIT + POSTGRESQL FIX
# Run this on the Raspberry Pi

set -e

echo "=========================================="
echo "🚀 STREAMLIT + POSTGRESQL DEPLOYMENT"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check if running on Raspberry Pi
echo -e "${YELLOW}[1/6] Checking environment...${NC}"
if [ ! -d "/home/pi" ]; then
    echo -e "${RED}❌ This script must run on Raspberry Pi!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Running on Raspberry Pi${NC}"

# 2. Install psycopg2 if missing
echo -e "${YELLOW}[2/6] Checking psycopg2...${NC}"
if python3 -c "import psycopg2" 2>/dev/null; then
    echo -e "${GREEN}✅ psycopg2 already installed${NC}"
else
    echo -e "${YELLOW}📦 Installing psycopg2-binary...${NC}"
    pip3 install psycopg2-binary
    echo -e "${GREEN}✅ psycopg2 installed${NC}"
fi

# 3. Backup old app.py
echo -e "${YELLOW}[3/6] Backing up old app.py...${NC}"
if [ -f "/home/pi/app.py" ]; then
    cp /home/pi/app.py "/home/pi/app.py.backup.$(date +%s)"
    echo -e "${GREEN}✅ Backup created${NC}"
fi

# 4. Copy new files
echo -e "${YELLOW}[4/6] Deploying new files...${NC}"
if [ -f "./app.py" ]; then
    cp ./app.py /home/pi/
    echo -e "${GREEN}✅ app.py deployed${NC}"
else
    echo -e "${RED}❌ app.py not found in current directory!${NC}"
    exit 1
fi

if [ -f "./diagnose_postgres.py" ]; then
    cp ./diagnose_postgres.py /home/pi/
    chmod +x /home/pi/diagnose_postgres.py
    echo -e "${GREEN}✅ diagnose_postgres.py deployed${NC}"
fi

# 5. Run diagnostic
echo -e "${YELLOW}[5/6] Running diagnostic...${NC}"
python3 /home/pi/diagnose_postgres.py

# 6. Restart Streamlit
echo -e "${YELLOW}[6/6] Restarting Streamlit...${NC}"
pkill -f "streamlit run app.py" || true
sleep 2

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "=========================================="
echo "🎯 NEXT STEPS"
echo "=========================================="
echo "1. Start Streamlit:"
echo "   streamlit run /home/pi/app.py"
echo ""
echo "2. Open browser:"
echo "   http://192.168.100.66:8502"
echo ""
echo "3. Check sidebar for status:"
echo "   🟢 Cloud (SQL) = Connected to PostgreSQL"
echo "   🟡 Local (CSV) = Using fallback CSV"
echo ""
echo "4. To test PostgreSQL fallback:"
echo "   docker compose down"
echo "   # Streamlit will switch to CSV mode"
echo "   docker compose up -d"
echo "   # Streamlit will switch back to SQL mode"
echo ""
echo "=========================================="
