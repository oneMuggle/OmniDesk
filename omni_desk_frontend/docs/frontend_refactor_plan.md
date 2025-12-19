# Frontend Refactoring Plan: `omni_desk_frontend/src`

## 1. Introduction

This document outlines a plan to refactor the `omni_desk_frontend/src` directory. The goal is to improve the project's structure, making it more scalable, maintainable, and easier for developers to navigate. The current structure mixes different concerns, leading to difficulties in locating files and understanding dependencies.

## 2. Current Directory Structure Analysis

The current `src` directory is organized primarily by file type, with major folders like `api`, `components`, `pages`, `hooks`, and `utils`.

```
src/
├── api/           # All API calls are grouped here
├── components/    # A mix of shared, feature-specific, and UI components
├── context/       # Global state management
├── features/      # An attempt at feature-based structure, but not fully adopted
├── hooks/         # Custom hooks for various features
├── pages/         # Top-level page components
├── routes/        # Routing configuration
├── styles/        # Global styles
├── types/         # Type definitions
└── utils/         # Utility functions for various features
```

**Problems with the current structure:**

*   **Low Cohesion:** Files related to a single feature (e.g., "schedule") are scattered across `api`, `components`, `hooks`, and `pages`. This makes it hard to understand the full scope of a feature.
*   **High Coupling:** Shared components are mixed with feature-specific ones, making it unclear what can be safely modified without causing side effects.
*   **Poor Scalability:** As new features are added, the top-level folders become increasingly cluttered, making navigation and maintenance difficult.
*   **Cognitive Overload:** Developers need to jump between many folders to work on a single feature.

## 3. Proposed Feature-Based Directory Structure

To address these issues, we propose a new structure organized by **features**. Each feature will have its own dedicated directory containing all related files (API, components, hooks, pages, etc.).

```
src/
├── features/
│   ├── authentication/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/       # e.g., LoginPage.jsx, RegisterPage.jsx
│   │   └── utils/
│   ├── schedule/
│   │   ├── api/
│   │   ├── components/  # e.g., CalendarContainer.jsx, EventModal.jsx
│   │   ├── hooks/
│   │   ├── pages/       # e.g., SchedulePage.jsx
│   │   ├── types/
│   │   └── utils/
│   ├── personnel/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   ├── sensor/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   └── ... (other features like meetingRoom, communication, etc.)
│
├── shared/
│   ├── api/           # For truly global API clients (e.g., axios instance)
│   ├── components/    # Reusable UI components (e.g., Button, Modal, Sidebar)
│   ├── context/       # Global contexts (e.g., AuthContext)
│   ├── hooks/         # Globally shared hooks
│   ├── styles/        # Global styles
│   ├── types/         # Shared type definitions
│   └── utils/         # Common utility functions
│
├── App.js
├── index.js
└── routes.js        # Centralized routing configuration
```

### Key Concepts of the New Structure:

*   **`features/`**: This is the core of the new structure. Each subdirectory represents a distinct feature or domain of the application (e.g., `authentication`, `schedule`, `personnel`).
*   **`shared/`**: This directory contains code that is genuinely shared across multiple features. This includes base UI components, global state, core API clients, and common utilities. This separation is crucial to prevent unintended coupling between features.

## 4. Migration Plan (File Mapping)

This section provides a high-level guide for migrating files from the old structure to the new one. **This plan does not involve moving files at this stage; it is for planning purposes only.**

| Old Path                                      | New Path                                        | Feature/Module      |
| --------------------------------------------- | ----------------------------------------------- | ------------------- |
| `api/schedule.js`, `api/scheduleEventApi.js`  | `features/schedule/api/`                        | Schedule            |
| `api/personnelApi.js`                         | `features/personnel/api/`                       | Personnel           |
| `api/userManagementApi.js`                    | `features/authentication/api/`                  | Authentication      |
| `api/axiosConfig.js`                          | `shared/api/`                                   | Shared              |
| `components/Calendar/CalendarContainer.jsx`   | `features/schedule/components/`                 | Schedule            |
| `components/Schedule/*`                       | `features/schedule/components/`                 | Schedule            |
| `components/Personnel/*`                      | `features/personnel/components/`                | Personnel           |
| `components/Sidebar.jsx`                      | `shared/components/`                            | Shared              |
| `pages/SchedulePage.jsx`                      | `features/schedule/pages/`                      | Schedule            |
| `pages/Login.jsx`                             | `features/authentication/pages/`                | Authentication      |
| `pages/PersonnelManagementPage.jsx`           | `features/personnel/pages/`                     | Personnel           |
| `hooks/useScheduleData.js`                    | `features/schedule/hooks/`                      | Schedule            |
| `context/AuthContext.js`                      | `shared/context/`                               | Shared              |
| `utils/dateUtils.js`                          | `shared/utils/`                                 | Shared              |
| `utils/scheduleUtils.js`                      | `features/schedule/utils/`                      | Schedule            |

## 5. Benefits of Refactoring

*   **Improved Maintainability:** Code is easier to find, understand, and modify.
*   **Enhanced Scalability:** Adding new features is as simple as creating a new directory under `features/` without cluttering the global scope.
*   **Better Developer Experience:** A logical and predictable structure reduces cognitive load and onboarding time for new developers.
*   **Clearer Boundaries:** The separation between `features` and `shared` makes dependencies explicit and helps prevent spaghetti code.

## 6. Next Steps

This document serves as the plan. The next phase would be to execute this plan by creating a separate task to perform the file migrations. It is recommended to perform the migration incrementally, feature by feature, to minimize disruption.