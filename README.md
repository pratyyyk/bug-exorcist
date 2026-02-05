# 🧟‍♂️ The Bug Exorcist 
**An autonomous AI agent that exorcises bugs from your codebase while you sleep.**

---

## 📖 Project Overview

**Bug Exorcist** is an autonomous system designed to haunt down and eliminate runtime errors. It actively listens for bugs, traps them in an isolated **Docker container** (sandbox) to reproduce the issue, and summons **GPT-4o** to write a patch. The agent then verifies the fix by re-running the code and, if successful, automatically commits the solution.

---

### 🛠️ Tech Stack

* **Frontend:** Next.js 14 (App Router), Tailwind CSS, Framer Motion
* **Backend:** Python (FastAPI), LangChain
* **Core Logic:** OpenAI GPT-4o + Docker SDK (Sandbox Management)

---

## 📂 Project Structure

We follow a modular monorepo structure. Please ensure your contributions are placed in the correct directories.

```text
├── frontend/                # Next.js 14 Application (User Dashboard)
│   ├── app/                 # App Router pages and layouts
│   ├── components/          # Reusable UI components
│   └── public/              # Static assets
│
├── backend/                 # FastAPI Server
│   ├── app/
│   │   ├── main.py          # Entry point
│   │   └── api/             # API routes
│   └── requirements.txt     # Python dependencies
│
├── core/                    # Autonomous Agent Logic
│   ├── agent.py             # LangChain & GPT-4o integration
│   └── sandbox/             # Docker SDK scripts for container management
│
├── docker-compose.yml       # Container orchestration
└── README.md                # Project Documentation
```

---

## ❄️ About AcWoC '26
This project is a featured repository in AcWoC (Android Club Winter of Code) 2026, an open-source initiative organized by the Android Club at VIT Bhopal.

Organizers: Android Club, VIT Bhopal

---

## 🤝 Contribution Guidelines
We welcome contributions from participants! To ensure a fair and organized workflow, please adhere strictly to the following rules.

### Issue Assignment & Fairness Policy

* First-Come, First-Served: Issues are assigned to the first contributor who comments asking for them.

* Wait for Assignment: Do not start working on an issue until a maintainer has explicitly assigned it to you.

* One Issue at a Time: You may only work on one assigned issue at a time.

### Pull Request (PR) Rules

* Link Your Issue: Every PR must be linked to the issue it solves (e.g., Closes #12).

* Descriptive Titles: Use clear titles like feat: Add dashboard sidebar or fix: Docker container timeout.

* Labeling: Maintainers will verify your PR and add the acwoc label along with a difficulty label (easy, medium, hard) to award points.
+1

### Reporting Issues

* If you find a bug or have a feature idea, please open an issue and tag the maintainers.

---

## 🚀 Getting Started

### Prerequisites

* Node.js & npm

* Python 3.10+

* Docker Desktop

### Installation

1. Clone the Repository
```
git clone [https://github.com/your-username/bug-exorcist.git](https://github.com/your-username/bug-exorcist.git)
cd bug-exorcist
```

2. Setup Backend
```
cd backend
pip install -r requirements.txt
python app/main.py
```

3. Setup Frontend
```
cd frontend
npm install
npm run dev
```
4. Run with Docker
```bash
# This builds the backend, frontend, and the sandbox image
docker-compose up --build
```

---

## 📬 Contact Maintainers

For questions regarding the project or AcWoC participation, please reach out via the AcWoC Discord Server.

---