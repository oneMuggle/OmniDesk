# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OmniDesk is a full-stack business management platform (Chinese-language UI) built with **Django 4.2** (backend) + **React 18.3** via CRA (frontend). Backend runs on port 8000, frontend on port 3000 (proxied).

## Essential Commands

### Backend (`omni_desk_backend/`)

```bash
# Dev server (uses settings.local by default)
python manage.py runserver

# Run tests (in-memory SQLite)
pytest --ds=omni_desk_backend.settings.test

# Compile dependencies (NEVER edit .txt files directly)
pip-compile -o requirements-prod.txt requirements.in    # prod deps
pip-compile -o requirements.txt requirements-dev.in     # dev deps
```

### Frontend (`omni_desk_frontend/`)

```bash
# Dev server (proxies /api to localhost:8000)
npm start

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint
npm run lint

# Build (auto-runs scripts/generate-routes.js first)
npm run build
```

## Architecture

### Backend Structure

Django settings are split across `omni_desk_backend/settings/`:
- `base.py` - shared config (DRF, JWT, CORS, Celery, i18n zh-hans)
- `local.py` - local dev (SQLite, DEBUG=True) - **default for manage.py**
- `development.py` - Docker dev (PostgreSQL at db:5432)
- `production.py` - production settings
- `test.py` - test (in-memory SQLite, MD5 password hasher, logging disabled)

Django apps: `personnel`, `events`, `documents`, `config`, `memos`, `dify_apps`, `office_assistant`, `projects`, `compliance`, `ragflow_service`, `meeting_rooms`, `sensor_management`, `communication`, `news`, `permissions`, `sensors`, `users`, `llm_service`

Custom user model: `AUTH_USER_MODEL = 'users.CustomUser'`

### Frontend Structure

- **Routing**: `createBrowserRouter` (React Router v6.4+) with lazy-loaded components. Routes defined in `src/routes/index.js`. Build step runs `scripts/generate-routes.js` to generate `public/routes.json`.
- **State**: TanStack React Query v5 for server state (5-min stale time, refetchOnWindowFocus: false). React Context for auth, API config, and page refresh. No Redux/Zustand.
- **API Layer**: Axios instance at `src/shared/api/axiosConfig.js` with baseURL `/api/`, JWT interceptor with automatic token refresh queue, and redirect to `/login` on refresh failure.
- **Auth**: JWT via `djangorestframework-simplejwt` (30-min access, 7-day refresh with rotation + blacklist). Tokens in localStorage/sessionStorage. `ProtectedRoute` checks page-level permissions.
- **UI**: Both **Ant Design 5** (primary) and **MUI** (secondary) are used simultaneously.

### CI/CD

- **main**: `build-and-push-images.yml` (Docker build + GHCR push) -> `deploy-ssh-windows.yml` (SSH deploy to Windows)
- **test**: `ci-test.yml` (backend pytest + frontend jest in parallel)
- **develop**: `ci-develop.yml` (separate backend/frontend jobs)

## Key Conventions & Gotchas

1. **Two UI libraries**: Ant Design and MUI coexist - check which is used in the module you're working on
2. **Frontend proxy**: `package.json` has `"proxy": "http://127.0.0.1:8000"` - API calls to `/api` are proxied
3. **Route auto-generation**: `npm run build` runs `scripts/generate-routes.js` via Babel AST parsing before building
4. **Test settings**: Uses in-memory SQLite with fast MD5 password hasher
5. **Root package.json**: Has Vue dependencies (extraneous) - frontend has its own package.json
6. **Django settings**: `manage.py` uses `settings.local` by default, NOT `settings.development`
7. **Backend requires PostgreSQL + Redis** for full functionality (Celery tasks)

## Environment Variables

### Frontend (`.env`)
```
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_OLLAMA_ENDPOINT=http://localhost:11434/api
REACT_APP_OLLAMA_MODEL=deepseek-r1:1.5b
```

### Backend
Uses environment variables for PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

## Agent Instructions

See `AGENTS.md` for comprehensive AI agent instructions including stack details, conventions, anti-patterns, and CI/CD details.
