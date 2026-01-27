# TuffWraps Marketing Attribution Dashboard

Production-grade marketing dashboard built with **Next.js** (frontend) and **FastAPI** (backend).

## Architecture

```
Marketing-Ads/
├── frontend/          # Next.js TypeScript app
│   ├── src/
│   │   ├── app/       # Pages (App Router)
│   │   ├── components/# Reusable UI components
│   │   └── lib/       # API client, utilities
│   └── package.json
│
├── backend/           # FastAPI Python backend
│   ├── main.py        # API entry point
│   ├── routers/       # API endpoints
│   ├── services/      # Business logic
│   └── requirements.txt
│
├── connectors/        # Data connectors & .env
│   ├── data/          # JSON data files
│   └── .env           # API keys
│
└── dashboard/         # Legacy Streamlit (deprecated)
```

## Quick Start

### 1. Install Dependencies

**Backend (Python):**
```bash
cd backend
pip install -r requirements.txt
```

**Frontend (Node.js):**
```bash
cd frontend
npm install
```

### 2. Configure Environment

Ensure your `connectors/.env` file has:
```
ANTHROPIC_API_KEY=your-key-here
```

### 3. Start the Servers

**Terminal 1 - Backend (port 8000):**
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend (port 3000):**
```bash
cd frontend
npm run dev
```

### 4. Open the Dashboard

Visit: http://localhost:3000

## Features

### Action Board
- **Specific campaign recommendations** with exact budget amounts
- **Auto-logging** - Check items and submit to automatically log to changelog
- Priorities: HIGH (scale), MEDIUM (watch), LOW (monitor)

### Command Center
- Overall health status based on CAM per order
- Today's action recommendation (Scale/Hold/Cut)
- Channel performance breakdown
- TOF assessment with proper metrics

### AI Chat
- Claude-powered marketing assistant
- Contextual answers based on your current data
- Quick question suggestions

### Activity Log
- Automatic logging from Action Board
- Manual entry support
- Full history with filtering

### CAM Performance
- Contribution After Marketing breakdown
- Channel-by-channel analysis
- Formula explanation

### TOF Analysis
- First-click attribution metrics
- NCAC tracking
- Branded search correlation
- Amazon halo effect

### Campaign Manager
- View all campaigns by channel
- Performance metrics (ROAS, orders, new customer %)

### Data Explorer
- Raw JSON data viewer
- Expandable tree structure

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/metrics/summary` | Quick summary of key metrics |
| `GET /api/metrics/signals` | Decision signals for action board |
| `GET /api/metrics/report` | Full CAM report |
| `GET /api/actions/list` | Action items with budget recommendations |
| `POST /api/actions/complete` | Log completed actions |
| `GET /api/changelog/entries` | Get changelog entries |
| `POST /api/changelog/entries` | Add new entry |
| `POST /api/ai/chat` | Chat with AI assistant |

## Tech Stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, Pydantic, Anthropic SDK
- **Data:** JSON files from marketing platform connectors
