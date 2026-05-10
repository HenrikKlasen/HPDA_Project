# HPDA Project - VAST Challenge 2022 (Challenge 3: Economic)

This project is a comprehensive visual analytics dashboard designed to solve **Challenge 3: Economic** of the **VAST Challenge 2022**. It provides an interactive, data-driven exploration of the financial health, employment dynamics, and urban economics of the fictional city of Engagement, Ohio.

## Tech Stack

- **Frontend**: React.js, Vite, D3.js (for custom charting and complex interactive maps), React Router for navigation.
- **Backend**: Python, Flask, Pandas (for data aggregation and metric derivation).
- **Database**: SQLite (housing the VAST Challenge 2022 datasets, including FinancialJournal, ParticipantStatusLogs, Jobs, Employers, Buildings, etc.).

## Project Structure

```text
HPDA_Project/
├── backend/                  # Python/Flask API server and data processing scripts
│   ├── server.py             # Main API server
│   ├── d3js.py               # Complex data aggregations and D3-ready HTML generation
│   └── database.py           # DB connection and queries
├── frontend/                 # React application
│   ├── public/               # Static assets and map data (JSON/CSV)
│   ├── src/
│   │   ├── components/       # Reusable UI components (Maps, Charts, Layout)
│   │   ├── pages/            # Main dashboard views
│   │   └── App.jsx           # Main application routing
└── README.md                 # This file
```

## Getting Started

### Prerequisites

- Node.js (v16+)
- Python 3.8+
- The required SQLite database file (`vast_challenge.db`) should be placed in the `backend/` directory.

### Running the Backend

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install the required Python packages (e.g., Flask, pandas, flask-cors):
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python server.py
   ```
   _(The backend server will run on port 5000 by default)._

### Running the Frontend

1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   _(The frontend will typically run on port 5173)._
