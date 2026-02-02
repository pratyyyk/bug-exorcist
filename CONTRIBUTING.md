# Contributing to Bug Exorcist 🧟‍♂️

Thank you for your interest in contributing to Bug Exorcist! This guide will help you get started and ensure your contributions are smoothly integrated into the project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Development Workflow](#development-workflow)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Getting Help](#getting-help)

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

1. **Python 3.10+**
   - Download from [python.org](https://www.python.org/downloads/)
   - Verify installation: `python --version`

2. **Node.js & npm**
   - Download from [nodejs.org](https://nodejs.org/) (v18+ recommended)
   - Verify installation: `node --version && npm --version`

3. **Docker Desktop**
   - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Verify installation: `docker --version`

4. **Git**
   - Download from [git-scm.com](https://git-scm.com/)
   - Verify installation: `git --version`

### API Keys Required

The Bug Exorcist requires AI API keys to function:

1. **OpenAI API Key** (Primary)
   - Sign up at [platform.openai.com](https://platform.openai.com/)
   - Create API key in your dashboard

2. **Google Gemini API Key** (Optional fallback)
   - Sign up at [ai.google.dev](https://ai.google.dev/)
   - Create API key in your dashboard

## Setup Instructions

### 1. Fork and Clone the Repository

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/bug-exorcist.git
cd bug-exorcist

# Add the original repository as upstream
git remote add upstream https://github.com/SamXop123/bug-exorcist.git
```

### 2. Environment Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit the .env file with your configuration
nano .env  # or use your preferred editor
```

**Required environment variables:**
```env
# AI Configuration
OPENAI_API_KEY=your-openai-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here

# Database
DATABASE_URL=sqlite:///./bug_exorcist.db

# Application Settings
DEBUG=True
ENVIRONMENT=development
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:3000

# Feature Flags
ENABLE_FALLBACK=true
ENABLE_GEMINI_FALLBACK=true
```

### 3. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi, openai, docker; print('Backend dependencies installed successfully')"
```

### 4. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install

# Verify installation
npm run build
```

### 5. Database Initialization

The SQLite database will be automatically created when you first run the backend. No additional setup is required.

## Development Workflow

### Running the Project Locally

You have two options to run the project:

#### Option 1: Manual Setup (Recommended for Development)

```bash
# Terminal 1: Start Backend
cd backend
python app/main.py
# Backend will be available at http://localhost:8000

# Terminal 2: Start Frontend
cd frontend
npm run dev
# Frontend will be available at http://localhost:3000
```

#### Option 2: Docker Compose

```bash
# From project root
docker-compose up --build
```

### Development URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Keeping Your Fork Updated

```bash
# Sync with upstream repository
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

## Project Structure

Understanding the project structure is crucial for effective contributions:

```
bug-exorcist/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── main.py          # FastAPI application entry point
│   │   ├── api/             # API route handlers
│   │   ├── models.py        # SQLAlchemy database models
│   │   ├── crud.py          # Database operations
│   │   ├── database.py      # Database configuration
│   │   ├── git_ops.py       # Git operations
│   │   └── sandbox.py       # Docker sandbox management
│   └── requirements.txt     # Python dependencies
├── frontend/               # Next.js React frontend
│   ├── app/                # App Router pages
│   ├── components/         # Reusable React components
│   ├── package.json        # Node.js dependencies
│   └── tsconfig.json       # TypeScript configuration
├── core/                   # Core AI agent logic
│   ├── agent.py           # Main Bug Exorcist agent
│   └── gemini_agent.py    # Gemini AI fallback
├── .env.example           # Environment template
├── docker-compose.yml     # Docker orchestration
└── README.md             # Project documentation
```

## Coding Standards

### Python Backend

- **Type Hints**: All functions must have proper type hints
- **Documentation**: Use docstrings for all functions and classes
- **Formatting**: Follow PEP 8 (use `black` formatter)
- **Linting**: Use `flake8` for code quality


### TypeScript Frontend

- **TypeScript**: Use strict TypeScript mode
- **Components**: Use functional components with hooks
- **Styling**: Use Tailwind CSS classes
- **Formatting**: Use Prettier

## Testing

### Backend Testing

```bash
# Run backend tests (when implemented)
cd backend
python -m pytest

# Run with coverage
python -m pytest --cov=app
```

### Frontend Testing

```bash
# Run frontend tests (when implemented)
cd frontend
npm test

# Run with coverage
npm run test:coverage
```

### Manual Testing

1. **API Testing**: Use the built-in Swagger UI at http://localhost:8000/docs
2. **Integration Testing**: Test the full bug analysis workflow
3. **Docker Testing**: Verify the application works in containers

## Submitting Pull Requests

### Before Submitting

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-number-description
   ```

2. **Make Your Changes**
   - Follow the coding standards
   - Add tests for new functionality
   - Update documentation if needed

3. **Test Your Changes**
   - Run all tests
   - Test manually in the browser
   - Ensure Docker build works

### Pull Request Guidelines

1. **Branch Naming**
   - Features: `feature/description`
   - Bug fixes: `fix/issue-number-description`
   - Documentation: `docs/update-description`

2. **Commit Messages**
   - Use conventional commits:
     - `feat: Add new bug analysis endpoint`
     - `fix: Resolve Docker container timeout issue`
     - `docs: Update contributing guidelines`

3. **Pull Request Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Unit tests pass
   - [ ] Manual testing completed
   - [ ] Docker build successful
   
   ## Related Issue
   Closes #issue-number
   
   ## Checklist
   - [ ] Code follows project style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   ```

4. **Review Process**
   - Maintainers will review your PR
   - Address feedback promptly
   - Keep the PR updated with the latest main branch

### After Submission

- Respond to reviewer comments in a timely manner
- Make requested changes and push updates
- Don't force push to PR branches after review starts

## Getting Help

### Resources

1. **Documentation**: Read the [README.md](README.md) for project overview
2. **API Documentation**: Visit http://localhost:8000/docs when running locally
3. **Issue Tracker**: Check [GitHub Issues](https://github.com/pratyyyk/bug-exorcist/issues)

### Communication Channels

1. **GitHub Issues**: For bug reports and feature requests
2. **Discord**: For general discussion and questions (if available)
3. **Pull Request Reviews**: For code-specific feedback

### Common Issues

**Docker Issues:**
```bash
# If Docker daemon is not running
# Start Docker Desktop application

# If port conflicts occur
# Check what's using the port:
netstat -tulpn | grep :8000  # Linux/macOS
netstat -ano | findstr :8000 # Windows
```

**Python Environment Issues:**
```bash
# If pip install fails
python -m pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir

# If import errors occur
# Ensure virtual environment is activated
# Check Python version compatibility
```

**Frontend Build Issues:**
```bash
# Clear npm cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

## Code of Conduct

Please be respectful and inclusive in all interactions. We're here to learn and build together!

---

Thank you for contributing to Bug Exorcist! Your contributions help make this project better for everyone. 🚀
