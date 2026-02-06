#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ██████╗ ██████╗  ██╗ █████╗ ███████╗ ██████╗ ██╗     ██╗"
echo " ██╔════╝ ╚════██╗███║██╔══██╗██╔════╝██╔═══██╗██║     ██║"
echo " ███████╗  █████╔╝╚██║╚██████║███████╗██║   ██║██║     ██║"
echo " ██╔═══██╗ ╚═══██╗ ██║ ╚═══██║╚════██║██║▄▄ ██║██║     ██║"
echo " ╚██████╔╝██████╔╝ ██║ █████╔╝███████║╚██████╔╝███████╗██║"
echo "  ╚═════╝ ╚═════╝  ╚═╝ ╚════╝ ╚══════╝ ╚══▀▀═╝ ╚══════╝╚═╝"
echo -e "${NC}"
echo -e "${GREEN}SQLMap Session Monitor - C2 Style Panel${NC}"
echo ""

INSTALL_DIR="${1:-/opt/6319sqli}"

echo -e "${YELLOW}[*] Installing to: $INSTALL_DIR${NC}"

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}[!] Please run as root (sudo)${NC}"
    exit 1
fi

PANEL_PORT=$(shuf -i 54209-60739 -n 1)
PANEL_PATH=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 34 | head -n 1)

echo -e "${YELLOW}[*] Generated port: $PANEL_PORT${NC}"
echo -e "${YELLOW}[*] Generated secret path: $PANEL_PATH${NC}"

echo -e "${YELLOW}[*] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv sqlmap git curl wget proxychains4 -qq

echo -e "${YELLOW}[*] Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo -e "${YELLOW}[*] Downloading 6319sqli...${NC}"
if [ -d ".git" ]; then
    git pull
else
    git clone https://github.com/44pie/6319_SQLi_c2.git .
fi

echo -e "${YELLOW}[*] Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${YELLOW}[*] Installing Python dependencies...${NC}"
pip install --upgrade pip -q
pip install streamlit pandas requests beautifulsoup4 streamlit-autorefresh -q

echo -e "${YELLOW}[*] Creating data directory...${NC}"
mkdir -p .6319sqli_data

echo -e "${YELLOW}[*] Saving panel access config...${NC}"
cat > .6319sqli_data/panel.json << EOF
{"port": $PANEL_PORT, "path": "$PANEL_PATH"}
EOF

echo -e "${YELLOW}[*] Creating Streamlit config...${NC}"
mkdir -p .streamlit
cat > .streamlit/config.toml << EOF
[server]
port = $PANEL_PORT
address = "0.0.0.0"
baseUrlPath = "$PANEL_PATH"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
base = "dark"
EOF

echo -e "${YELLOW}[*] Creating systemd service...${NC}"
cat > /etc/systemd/system/6319sqli.service << EOF
[Unit]
Description=6319sqli SQLMap Monitor Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/streamlit run app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo -e "${YELLOW}[*] Enabling and starting service...${NC}"
systemctl daemon-reload
systemctl enable 6319sqli
systemctl start 6319sqli

IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}[+] Installation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Access panel: http://$IP:$PANEL_PORT/$PANEL_PATH${NC}"
echo ""
echo -e "${RED}SAVE THIS! Port and path are random and won't be shown again.${NC}"
echo -e "${RED}Config saved to: $INSTALL_DIR/.6319sqli_data/panel.json${NC}"
echo ""
echo -e "Commands:"
echo -e "  ${YELLOW}systemctl status 6319sqli${NC}  - Check status"
echo -e "  ${YELLOW}systemctl restart 6319sqli${NC} - Restart panel"
echo -e "  ${YELLOW}systemctl stop 6319sqli${NC}    - Stop panel"
echo -e "  ${YELLOW}journalctl -u 6319sqli -f${NC}  - View logs"
echo -e "  ${YELLOW}cat $INSTALL_DIR/.6319sqli_data/panel.json${NC}  - View access info"
echo ""
