# OmniDesk Agent Instructions

## Project Overview

Full-stack Django + React monorepo. Backend runs on port 8000, frontend on port 3000 (proxied).

## Running Commands

```bash
# Backend (requires PostgreSQL + Redis running)
cd omni_desk_backend
python manage.py runserver

# Frontend
cd omni_desk_frontend
npm start

# Run tests
# Backend: uses in-memory SQLite
cd omni_desk_backend
pytest --ds=omni_desk_backend.settings.test

# Frontend
cd omni_desk_frontend
npm test

# Frontend lint
cd omni_desk_frontend
npm run lint
```

## Django Settings

Settings are split across multiple files in `omni_desk_backend/omni_desk_backend/settings/`:
- `base.py` - shared config
- `development.py` - dev (Docker PostgreSQL at `db:5432`)
- `production.py` - prod
- `test.py` - test (in-memory SQLite)

To run with a specific settings module:
```bash
python manage.py runserver --settings=omni_desk_backend.settings.development
# or
pytest --ds=omni_desk_backend.settings.test
```

## Dependency Management

### Backend - pip-compile (NEVER edit .txt files directly)

```bash
cd omni_desk_backend
pip-compile -o requirements-prod.txt requirements.in   # prod deps
pip-compile -o requirements.txt requirements-dev.in  # dev deps
```

Edit `.in` files first, then regenerate.

### Frontend - standard npm

Uses react-scripts (CRA). Route generation happens at build time via `scripts/generate-routes.js`.

## Key Tech Stack

- **Backend**: Django 3.2, DRF, PostgreSQL, Redis (Celery), CORS headers, JWT (simplejwt)
- **Frontend**: React (CRA), React Router, TanStack Query, Ant Design, MUI, axios
- **Auth**: JWT stored in localStorage

## Non-Obvious Conventions

1. **Two UI libraries**: Both Ant Design and MUI are used in the frontend
2. **Frontend proxy**: `package.json` has `"proxy": "http://127.0.0.1:8000"` - API calls relative to `/api` work
3. **Route auto-generation**: `npm run build` runs `scripts/generate-routes.js` first
4. **Test settings**: Uses in-memory SQLite, fast password hasher (MD5), logging disabled

## Environment Variables

### Frontend (.env)
```
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_OLLAMA_ENDPOINT=http://localhost:11434/api
REACT_APP_OLLAMA_MODEL=deepseek-r1:1.5b
```

### Backend
Uses environment variables for PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

## CI/CD

- **Push to main**: Triggers `build-and-push-images.yml` (builds Docker, pushes to GHCR) → `deploy-ssh-windows.yml` (SSH deploy)
- **Push to test**: Triggers `ci-test.yml` (backend pytest + frontend jest)

## App Structure

### Backend Apps
`personnel`, `events`, `documents`, `config`, `memos`, `dify_apps`, `office_assistant`, `projects`, `compliance`, `ragflow_service`, `meeting_rooms`, `sensor_management`, `communication`, `news`, `permissions`, `sensors`

### Frontend Routes
Auto-generated from `src/routes/` - check that directory for available pages.

## Entry Points

### Backend (Django)
- `omni_desk_backend/manage.py` - CLI entry point (uses local settings by default)
- `omni_desk_backend/omni_desk_backend/settings/local.py` - Dev config (NOT development.py)
- `omni_desk_backend/omni_desk_backend/urls.py` - API routing
- `omni_desk_backend/omni_desk_backend/wsgi.py` - WSGI bootstrap
- `omni_desk_backend/omni_desk_backend/asgi.py` - ASGI bootstrap

### Frontend (React)
- `omni_desk_frontend/src/index.js` - CRA bootstrap with RouterProvider (v6.4+ style)
- `omni_desk_frontend/src/App.js` - Main layout with Sidebar + Outlet
- `omni_desk_frontend/src/routes/index.js` - Route config via createBrowserRouter

## Anti-Patterns (THIS PROJECT)

- No "DO NOT"/"NEVER"/"TODO" markers found in code comments (clean)
- Root-level `node_modules/` and `package.json` with Vue deps (unusual - frontend has its own)
- Multiple deployment strategies maintained in parallel (Docker, Gunicorn, Nginx Unit) - high maintenance burden

## CI/CD Details

- **Main branch**: `build-and-push-images.yml` → `deploy-ssh-windows.yml` (Windows SSH deploy)
- **Test branch**: `ci-test.yml` (parallel backend pytest + frontend jest)
- **Develop branch**: `ci-develop.yml` (separate backend/frontend jobs)
- **Windows deployment**: SSH to Windows server, pulls from GHCR (unusual for Django)

## Notes

- Root has extraneous `package.json` with Vue dependencies - frontend has its own
- Django settings module is `local.py` not `development.py`
- React uses createBrowserRouter with `future` flag (v7 transition)
- Build: `npm run build` auto-runs `scripts/generate-routes.js` to generate `public/routes.json`