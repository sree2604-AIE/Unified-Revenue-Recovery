# Unified Revenue Recovery Orchestrator

![Dashboard Preview](frontend/src/assets/hero.png)

> An AI-driven intervention orchestrator for payment declines, checkout abandons, and overdue receivables. Built for the Razorpay AI Intern Buildathon (Track 3: Revenue Recovery).

Traditional revenue recovery systems operate as "blunt instruments." They blindly spam customers with retries every 24 hours, burning through limited retry budgets, ignoring compliance opt-outs, and treating all failures identically. 

The **Unified Revenue Recovery Orchestrator** replaces blind retries with an AI-driven, context-aware decision engine that "thinks before it acts."

## 🚀 Key Objectives & Solutions

1. **Strategic Mandate Budgeting:** Treats NPCI UPI mandate retry limits as a scarce, tactical resource. Instead of spamming retries, the AI analyzes transaction history to predict a customer's optimal payday, holding the retry until the probability of success is highest.
2. **Root-Cause Routing:** Categorizes every failure precisely (e.g., checkout drop-off vs. bank timeout vs. suspected fraud) and maps it to a specific, tailored recovery action rather than a one-size-fits-all approach.
3. **Ironclad Compliance Guardrails:** Enforces priority stopping rules before any recovery action is taken. If a user opts out, the engine executes an immediate "hard stop"—prioritizing user trust over short-term revenue metrics.
4. **100% Explainability:** AI in fintech requires trust. Our system features a Live Execution Audit Trail and a transparent Decision Rules panel, documenting exactly *why* the AI made every single choice, making it fully auditable for merchants.

## 🛠 Tech Stack

- **Frontend:** React (Vite), JavaScript, Vanilla CSS. Features a dynamic, real-time command center dashboard.
- **Backend:** Python, FastAPI. Houses the core Decision Engine, Rule Evaluators, and data simulation.

## ⚙️ Running Locally

The project is split into a frontend and a backend. Both need to be running simultaneously.

### 1. Start the Backend (FastAPI)
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### 2. Start the Frontend (React)
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Navigate to `http://localhost:5173` in your browser. Click the **"Run New Batch"** button in the top right to simulate incoming failed payments and watch the AI orchestrator process them in real-time.

## 📂 Project Structure

- `/backend` - The brain of the operation. Contains the `decision_engine.py` which houses the core logic, compliance checks, and recovery strategy routing.
- `/frontend` - The command center UI. Visualizes the real-time metrics, recovery breakdowns, the mandate budget tracker, and the live audit trail.
