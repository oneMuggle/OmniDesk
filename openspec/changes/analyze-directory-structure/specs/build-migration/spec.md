# Specification: Build Tool Migration (CRA to Vite)

## ADDED Requirements

### Requirement: Vite as build tool
The project SHALL use Vite as the build and development tool.

#### Scenario: Vite installs correctly
- **WHEN** `@vitejs/plugin-react` is installed
- **THEN** Vite is functional in project

#### Scenario: Development server runs
- **WHEN** `npm run dev` executes (with Vite)
- **THEN** dev server starts on port 3000

#### Scenario: Production build succeeds
- **WHEN** `npm run build` executes (with Vite)
- **THEN** production build completes without errors

### Requirement: Vite configuration
The project SHALL have a valid vite.config.js.

#### Scenario: Proxy configuration
- **WHEN** vite.config.js includes API proxy
- **THEN** API calls proxy to backend correctly

#### Scenario: React plugin works
- **WHEN** Vite loads with @vitejs/plugin-react
- **THEN** JSX/TSX files are transformed correctly

## MODIFIED Requirements

### Requirement: Build scripts
The project SHALL use Vite commands in package.json scripts.

#### Scenario: Build script updated
- **WHEN** `package.json` scripts are updated
- **THEN** scripts use `vite build` instead of `react-scripts build`

#### Scenario: Dev server script
- **WHEN** dev script runs
- **THEN** `vite` starts development server

## REMOVED Requirements

### Requirement: CRA (react-scripts) support
**Reason**: CRA is deprecated, no longer maintained
**Migration**: Use Vite for all builds

## Open Questions

1. Should route generation move to Vite plugin or separate script?
2. How to handle environment variables in Vite?
3. What happens to existing webpack-specific code?