# Contributing to Bug Exorcist

Thanks for contributing. This guide explains how to propose changes, set up the project, and submit a clean PR.

## Ways to Contribute
* Report bugs and regressions
* Suggest features or improvements
* Improve docs and examples
* Fix issues and add tests

## Before You Start
* Search existing issues and PRs to avoid duplicates
* Open an issue for anything beyond a small doc fix
* Wait for maintainer feedback if the change is large or risky

## Development Setup

### Prerequisites
* Python 3.10+
* Node.js 18+ and npm
* Docker Desktop

### Clone and Configure
```bash
git clone https://github.com/YOUR_USERNAME/bug-exorcist.git
cd bug-exorcist
cp .env.example .env
```

### Backend Setup
```bash
cd backend
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm ci
npm run dev
```

## Project Structure
```
backend/   FastAPI server, database, sandbox
core/      AI agent logic
frontend/  Next.js app
tests/     Python tests
```

## Coding Standards
* Python formatting: `black`
* Python linting: `ruff`
* TypeScript linting: `npm run lint`

## Testing
```bash
python -m pytest
```

Frontend checks:
```bash
cd frontend
npm run lint
npm run build
```

## Branching and Commits
* Branch names: `feature/...`, `fix/...`, `docs/...`
* Use conventional commits when possible

## Pull Request Checklist
* Link the related issue
* Keep the PR focused and small
* Add tests or explain manual verification
* Update docs if behavior changes

## Review Process
* Maintainers may request changes
* Keep commits clean and respond to feedback

## Code of Conduct
Be respectful and collaborative. We want a welcoming community.
