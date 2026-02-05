# 6319sqli - SQLMap Session Monitor

C2-style web panel for monitoring SQLMap injection sessions with Nord theme.

![6319sqli Panel](https://img.shields.io/badge/SQLMap-Monitor-blue)

## Features

- Real-time SQLMap output monitoring
- Nord dark theme with JetBrains Mono font
- Host list with injection status (VULNERABLE/NOT INJ)
- Quick action buttons (--dbs, --tables, --dump, etc.)
- Multiple tab support (INFO, SQLMAP, LOG, DUMPS)
- Multi-threaded session management

## Quick Install (Ubuntu/Debian)

```bash
curl -sSL https://raw.githubusercontent.com/44pie/6319_SQLi_c2/main/install.sh | sudo bash
```

Or specify custom directory:

```bash
curl -sSL https://raw.githubusercontent.com/44pie/6319_SQLi_c2/main/install.sh | sudo bash -s /custom/path
```

## Manual Install

```bash
git clone https://github.com/44pie/6319_SQLi_c2.git
cd 6319_SQLi_c2
pip install streamlit pandas requests beautifulsoup4
streamlit run app.py --server.port 5000
```

## Usage

1. Create SQLMap output directory: `/opt/6319sqli/ttt/sql_out/`
2. Run SQLMap with output dir: `sqlmap -u "URL" --output-dir=/opt/6319sqli/ttt/sql_out/target.com`
3. Access panel at `http://YOUR_IP:5000`

## Service Commands

```bash
systemctl status 6319sqli   # Check status
systemctl restart 6319sqli  # Restart
systemctl stop 6319sqli     # Stop
journalctl -u 6319sqli -f   # View logs
```

## Requirements

- Python 3.8+
- SQLMap
- Ubuntu/Debian (for auto-install)

## License

MIT
