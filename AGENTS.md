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

Uses Vite 5.4 (the CRA-to-Vite migration is complete; `package.json` proxy field is obsolete). Route generation happens at build time via `scripts/generate-routes.js`.

## Key Tech Stack

- **Backend**: Django 4.2, DRF, PostgreSQL, Redis (Celery), CORS headers, JWT (simplejwt)
- **Frontend**: React 18.3 + Vite 5.4, React Router v6.4, TanStack Query v5, Ant Design 5, axios
- **Auth**: JWT stored in localStorage

## Non-Obvious Conventions

1. **UI library**: Ant Design 5 is the only UI library in use (120 imports under `src/`); MUI has been removed
2. **Frontend proxy**: `vite.config.js` has `server.proxy` mapping `/api` to `http://127.0.0.1:8000`; the legacy `package.json` proxy field is deprecated
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

- **Push to main**: Triggers `build-and-push-images.yml` (builds Docker, pushes to GHCR) → `deploy-test.yml` (Deploy Test via workflow_run)
- **Push / PR to main & develop**: Triggers `ci.yml` (unified CI: backend pytest + frontend jest + lint + mypy)

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
- `omni_desk_backend/<app>/ai_tools.py` - 各 app 的 AI 工具声明，由 `smart_assistant/capabilities` 自动发现；清单见 `docs/technical/46-ai-capability-catalog.md`（`python manage.py ai_capabilities --write` 生成）

### Frontend (React)
- `omni_desk_frontend/src/index.jsx` - Vite entry, bootstraps RouterProvider (v6.4+ style)
- `omni_desk_frontend/src/App.jsx` - Main layout with Sidebar + Outlet
- `omni_desk_frontend/src/routes/index.jsx` - Route config via createBrowserRouter
- `omni_desk_frontend/src/features/admin/config/adminRoutePermissions.js` - `/control-panel/*` 路由权限单一数据源（路由守卫 / 管理菜单 / 搜索结果共用）

## Anti-Patterns (THIS PROJECT)

- No "DO NOT"/"NEVER"/"TODO" markers found in code comments (clean)
- Multiple deployment strategies maintained in parallel (Docker, Gunicorn, Nginx Unit) - high maintenance burden

## CI/CD Details

- **Main branch**: `build-and-push-images.yml` (Docker build + GHCR push) → `deploy-test.yml` (via workflow_run)
- **Main & develop branches / PRs**: `ci.yml` (unified CI: parallel backend pytest + frontend jest + lint + mypy; the legacy `ci-test.yml` has been removed)
- **Windows deployment**: SSH to Windows server, pulls from GHCR (unusual for Django)

## Notes

- Root `package.json` / `package-lock.json` are git-ignored (the old Vue-deps note is obsolete since 2026-06); the frontend has its own
- Django settings module is `local.py` not `development.py`
- React uses createBrowserRouter with `future` flag (v7 transition)
- Build: `npm run build` auto-runs `scripts/generate-routes.js` to generate `public/routes.json`