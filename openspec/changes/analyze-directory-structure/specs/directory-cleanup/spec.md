# Specification: Directory Structure Cleanup

## ADDED Requirements

### Requirement: Unified documentation structure
The project SHALL have a single documentation directory.

#### Scenario: docs/ is primary
- **WHEN** documentation is needed
- **THEN** docs/ contains all documentation

#### Scenario: tech_docs/ merged
- **WHEN** tech_docs/ content is moved to docs/
- **THEN** tech_docs/ directory is removed

### Requirement: Clean tool directories
Tool-specific directories SHALL remain separate.

#### Scenario: .cospec/ remains
- **WHEN** CoSpec tool is used
- **THEN** .cospec/ contains tool configuration

#### Scenario: .opencode/ remains
- **WHEN** OpenCode tool is used
- **THEN** .opencode/ contains tool configuration

## MODIFIED Requirements

### Requirement: Deployment directories
The deployment/ directory SHALL contain only active configurations.

#### Scenario: Unused configs removed
- **WHEN** unused deployment configs are removed
- **THEN** only Docker and active configs remain

## REMOVED Requirements

### Requirement: tech_docs/ as separate directory
**Reason**: Functionally overlaps with docs/
**Migration**: Content moved to docs/technology/

## Non-Goals

- No changes to source code directories (omni_desk_backend/, omni_desk_frontend/)
- No changes to scripts/ (active build/deploy scripts)
- No removal of .cospec/ or .opencode/ (tool directories)