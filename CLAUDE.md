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

- **main**: `build-and-push-images.yml` (Docker build + GHCR push)
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

## Version Update System

This project has a version management and safe update system located in the `core` Django app and deployment scripts.

### Version Numbering
- Uses **Semantic Versioning** (`MAJOR.MINOR.PATCH`) defined in `deployment/docker/VERSION`
- The `core/version.py` module reads this file at Django startup and exposes `APP_VERSION` in settings
- **Never** use `:latest` Docker image tags in production — use semantic version tags (e.g., `v1.0.0`)
- **Always** update `VERSION` and `deployment/docker/CHANGELOG.md` when adding new features or making breaking changes

### Django Management Commands (core app)
| Command | Purpose |
|---------|---------|
| `python manage.py check_migrations` | Pre-check pending migrations; warns about destructive changes (DROP TABLE/COLUMN) |
| `python manage.py backup_db` | Backup database (pg_dump + gzip) and media files; auto-cleans old backups (keeps 10) |
| `python manage.py restore_db <file>` | Restore database from a `.sql.gz` backup file |
| `python manage.py list_versions` | Show current version and migration history summary |

### API Endpoints
| Endpoint | Auth | Returns |
|----------|------|---------|
| `GET /api/system/version/` | Authenticated | `{version, build_time, django_version}` |
| `GET /api/system/changelog/` | Authenticated | `{changelog: "markdown content"}` |
| `GET /api/system/migrations/` | Authenticated | `{applied: [], pending: [], has_destructive: bool}` |

### Frontend
- **System Update Page**: `/control-panel/system-update` (admin menu, requires `admin` permission)
- Component: `omni_desk_frontend/src/shared/pages/SystemUpdatePage.jsx`
- Displays version info, rendered changelog, and migration status with destructive change warnings

### Deployment Scripts
| Script | Purpose |
|--------|---------|
| `deployment/docker/upgrade.sh` | Safe 10-step upgrade: check → load images → pre-check migrations → confirm → backup → update → migrate → health check |
| `deployment/docker/rollback.sh` | Rollback to previous version with optional DB restore |
| `deployment/docker/backup.sh` | Manual backup wrapper around `backup_db` command |
| `deploy_offline.sh` | Added sub-commands: `version`, `backup`, `upgrade`, `rollback`, `migrate` |

### Update Rules
1. **Backup before every update** — run `backup_db` or `./backup.sh` before `migrate`
2. **Pre-check migrations** — always run `check_migrations` first; if destructive changes are detected, require manual review
3. **Major version upgrades** (`1.x → 2.x`) must NOT use `upgrade.sh` — they require a manual migration plan
4. **CHANGELOG.md** must be updated for every released version
5. Migration safety: Django migrations are NOT auto-applied on app startup; they must be run explicitly via `migrate`

## Development Workflow

### Plan-First Rule
**ALL** feature additions and significant code changes MUST follow this workflow:

1. **Write a plan document first** — output to `docs/plans/` with filename format: `YYYY-MM-DD_short-description.md`
2. **Wait for approval** — do NOT start coding until the plan is confirmed by the user
3. **Implement step by step** — follow the plan's phases/tasks sequentially
4. **Update progress in the plan** — mark each step as `[x]` when completed
5. **Finalize** — when all steps are done, the plan document serves as a record

### Plan Document Structure
Each plan must include:
- Background & objectives
- Affected files and modules
- Technical approach (architecture, interfaces, data flow)
- Implementation steps (checkbox list, phased)
- Risks and dependencies

### Exceptions (no plan needed)
- Bug fixes (single file, obvious fix)
- Style/formatting changes
- Documentation-only updates
- Dependency version bumps (non-breaking)

### Archive Completed Plans
When a feature is fully implemented, move its plan from `docs/plans/` to `docs/technical/` or keep in `docs/plans/` with all steps checked.

## Intranet & Compatibility Requirements

This project is deployed on isolated internal networks and must be accessible from Windows 7 machines.

### Offline-First Rule
**ALL** build artifacts and dependencies MUST be fully self-contained — no external network access is available in production.

- **No CDN references** — all libraries (Ant Design, React, etc.) must be bundled locally via npm/yarn
- **No external API calls** — all data must come from the backend or internal services
- **No external resource loading** — fonts, icons, images, scripts must all be bundled
- **Docker images must be exportable** — use `docker save` to produce `.tar` files for offline transfer
- **Dependency installation happens on the build machine, not the target server**

### Windows 7 Compatibility
The site must work correctly on Windows 7 browsers (Chrome 109 / Edge 109 max, possibly IE11):

- **Do NOT drop IE11 support** — avoid using features that break in IE11 unless explicitly approved
- **React build target** — ensure `package.json` browserslist includes Windows 7 compatible browsers
- **Avoid modern JS features** not supported in Chrome 109: check ES2022+ features before use
- **Avoid CSS features** not supported in older browsers (e.g., `:has()`, container queries) without fallbacks
- **Test with Chrome 109** when possible, or use polyfills for missing features
- **Frontend build config** — verify CRA output does not emit syntax unsupported by target browsers

## Language

**All conversation and documentation MUST use Chinese (中文).**

This includes:
- Progress reports and summaries
- Plan documents and technical descriptions
- Commit messages and PR descriptions
- Code comments (when needed)
- UI text and error messages

**Exceptions:** Code identifiers, technical terms (API, TypeScript, React, etc.), and command output may remain in their original language.
