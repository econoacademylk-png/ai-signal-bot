# AI Crypto Trading Bot (Electron + Flask)

An intelligent cryptocurrency trading bot featuring a modern React/Electron desktop interface, Smart Money Concepts (SMC), chart pattern detection, machine learning price predictions, and automated Binance execution with Telegram alerts.

---

## 🚀 Features

- **Desktop GUI**: Built with React, Vite, Tailwind CSS, and Electron.
- **Python Backend**: High-performance market analysis powered by CCXT, Scikit-Learn, and Technical Analysis (ta).
- **Strategy & Analysis**:
  - Technical indicators (RSI, MACD, Moving Averages).
  - Smart Money Concepts (SMC) & Order Blocks.
  - Chart pattern detection.
  - Random Forest Machine Learning prediction.
- **Automated Trading**: Integration with Binance (Testnet & Live support via CCXT).
- **Alerts**: Real-time Telegram notifications for signal generation, entries, take-profit, and stop-loss.

---

## 📁 Project Structure

`	ext
aibot/
├── backend/                  # Python Flask API & Bot Engine
│   ├── app.py               # Flask REST API server
│   ├── bot.py               # Main bot loop, indicators & execution
│   ├── pattern_detector.py  # Chart pattern detection
│   ├── smc_detector.py      # Smart Money Concepts analysis
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Template for environment variables
├── frontend/                 # Electron + React GUI
│   ├── electron/            # Electron main process
│   ├── src/                 # React UI components & state
│   ├── package.json         # Node.js dependencies
│   └── vite.config.mjs      # Vite configuration
└── README.md
`

---

## 🛠️ Setup & Installation

### 1. Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) (v3.9+)
- Binance Account & API keys (Testnet recommended for testing)
- Telegram Bot Token & Chat ID (Optional for alerts)

---

### 2. Backend Setup

`ash
# Navigate to backend directory
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
`

Open .env in ackend/ and provide your credentials:
`env
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
USE_TESTNET=true

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
`

Start the backend:
`ash
python app.py
`

---

### 3. Frontend Setup

`ash
# Navigate to frontend directory
cd frontend

# Install npm dependencies
npm install

# Run the desktop application in development mode
npm run electron:dev
`

---

## ⚠️ Disclaimer

Trading cryptocurrencies involves substantial risk and can result in the loss of your invested capital. This software is for educational and research purposes only. Always test thoroughly on Testnet before using real funds.
