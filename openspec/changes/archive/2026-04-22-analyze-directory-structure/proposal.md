# Proposal: Directory Structure Optimization

## Why

The OmniDesk project has accumulated technical debt in its directory organization, including:
- Potential redundant dependencies (moment.js, react-query, dual calendar libraries)
- Mixed UI libraries (Ant Design + MUI)
- Duplicate documentation directories (docs/, tech_docs/, .cospec/wiki/)
- Build tool using deprecated CRA

After analysis:
- moment.js and react-query (v3) were already removed
- Both calendar libraries are used by different pages (cannot consolidate)
- MUI was not installed in the project
- CRA still works, Vite migration deferred

## Capabilities

### New Capabilities

- **dependency-audit**: Automated detection of redundant/outdated dependencies
- **directory-cleanup**: Streamlined project structure with clear separation of concerns

### Modified Capabilities

- (None - this is a maintenance change, not a feature change)

## Impact

### Backend (omni_desk_backend/)
- No changes to application code
- Python dependencies remain stable (Django 3.2, DRF, PostgreSQL, Redis)

### Frontend (omni_desk_frontend/)
- Package.json: Remove redundant dependencies
- Component migration: MUI → Ant Design
- Build optimization: CRA → Vite

### Documentation
- Consolidate docs/, tech_docs/, .cospec/wiki/ into unified structure

### CI/CD
- Enhanced with parallel testing and security scanning

## Non-Goals

This proposal does NOT include:
- Backend framework migration (Django 3.2 is stable)
- Database schema changes
- API breaking changes
- New feature development
- User-facing functionality changes

## Verification

- [ ] Backend: `pytest --ds=omni_desk_backend.settings.test` passes
- [ ] Frontend: `npm test` passes
- [ ] Frontend: `npm run lint` passes
- [ ] Build: `npm run build` completes successfully
- [ ] No regression in feature functionality