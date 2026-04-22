# Design: Directory Structure Optimization

## Context

The OmniDesk project has been in active development, accumulating technical debt in:
1. **Dependencies**: package.json contains redundant/outdated packages
2. **UI Libraries**: Both Ant Design and MUI are used
3. **Documentation**: Multiple overlapping directories
4. **Build Tool**: Uses deprecated CRA

Current package.json issues:
- moment.js (deprecated)
- react-query (duplicate of @tanstack/react-query)
- @fullcalendar/* + react-big-calendar (duplicate calendar libs)

## Goals / Non-Goals

**Goals:**
1. Remove redundant/outdated npm dependencies
2. Migrate from MUI to Ant Design for UI consistency
3. Simplify documentation directory structure
4. Migrate build tool to Vite

**Non-Goals:**
- No backend changes
- No database schema changes
- No API breaking changes
- No new features

## Decisions

### 1. Dependency Cleanup

| Library | Action | Rationale |
|---------|--------|-----------|
| moment.js | Remove | Deprecated, use date-fns or dayjs |
| react-query | Remove | Duplicate of @tanstack/react-query |
| @fullcalendar/* | Remove | Keep react-big-calendar |
| react-big-calendar | Keep | Already integrated |

### 2. UI Library Unification

| Library | Action | Rationale |
|---------|--------|-----------|
| Ant Design | Keep | Primary UI library |
| @mui/material | Remove | Migrate to Ant Design equivalents |

**Migration Strategy:**
- Identify MUI usage in codebase
- Replace with Ant Design components
- Update styles to use Ant Design tokens

### 3. Documentation Consolidation

| Directory | Action |
|-----------|--------|
| docs/ | Keep (primary) |
| tech_docs/ | Merge into docs/ |
| .cospec/wiki/ | Keep (tool-specific) |

### 4. Build Tool Migration

| From | To | Rationale |
|------|-----|---------|
| CRA (react-scripts) | Vite | CRA deprecated, no security updates |

**Migration Phases:**
1. Install Vite dependencies
2. Create vite.config.js
3. Migrate index.js entry point
4. Test and verify

## Risks / Trade-offs

1. **Migration Breakage Risk** → Mitigation: Full test coverage before migration
2. **Dependency Conflicts** → Mitigation: Clean install after removal
3. **UI Breaking Changes** → Mitigation: Component-by-component migration with testing

## Migration Plan

### Phase 1: Dependency Cleanup (P0)
```bash
npm uninstall moment react-query @fullcalendar/core @fullcalendar/daygrid @fullcalendar/interaction @fullcalendar/react @fullcalendar/timegrid react-big-calendar
```

### Phase 2: UI Unification (P1)
- Scan MUI components in use
- Create Ant Design equivalents
- Migrate one page at a time

### Phase 3: Build Tool Migration (P2)
- Install @vitejs/plugin-react
- Create vite.config.js
- Adjust package.json scripts

### Phase 4: Documentation (P1)
- Merge tech_docs/ into docs/
- Update references

## Verification

- [ ] `npm test` passes after each phase
- [ ] `npm run lint` passes
- [ ] `npm run build` succeeds
- [ ] Manual testing of关键页面