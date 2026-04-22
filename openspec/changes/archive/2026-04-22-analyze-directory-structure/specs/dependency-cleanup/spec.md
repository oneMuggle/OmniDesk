# Specification: Dependency Cleanup

## ADDED Requirements

### Requirement: Remove deprecated moment.js library
The project SHALL remove moment.js from dependencies as it is deprecated.

#### Scenario: Remove moment.js
- **WHEN** `npm uninstall moment` is executed
- **THEN** moment.js is removed from package.json and node_modules

#### Scenario: Verify no moment.js usage
- **WHEN** grep searches for 'moment' in source files
- **THEN** no import statements using moment should exist

### Requirement: Remove duplicate react-query
The project SHALL remove react-query as it duplicates @tanstack/react-query.

#### Scenario: Remove react-query package
- **WHEN** `npm uninstall react-query` is executed
- **THEN** react-query is removed from package.json

#### Scenario: Verify @tanstack/react-query works
- **WHEN** application runs with @tanstack/react-query only
- **THEN** all query functionality works correctly

### Requirement: Remove duplicate calendar libraries
The project SHALL use only one calendar library.

#### Scenario: Remove FullCalendar packages
- **WHEN** `@fullcalendar/*` packages are uninstalled
- **THEN** all FullCalendar imports are removed from codebase

#### Scenario: Keep react-big-calendar
- **WHEN** react-big-calendar is retained
- **THEN** calendar functionality continues to work

## REMOVED Requirements

### Requirement: moment.js support
**Reason**: Library is deprecated and no longer maintained
**Migration**: Use date-fns or dayjs for date operations

### Requirement: react-query (v3) support
**Reason**: Duplicate of @tanstack/react-query
**Migration**: Use @tanstack/react-query v5