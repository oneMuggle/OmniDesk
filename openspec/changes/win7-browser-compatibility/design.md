## Context

- **Current State**: Frontend uses React 18 with Create React App (react-scripts 5.0.1). Browserslist targets `">0.2%", "not dead"` which excludes Firefox 115 ESR.
- **Target Environment**: Windows 7 users with Firefox 115 ESR (the only browser with support until August 2026)
- **Dependencies**: Ant Design 5.x, MUI 5.x, TanStack Query 5.x, react-router-dom 6.x

## Goals / Non-Goals

**Goals:**
- Make the frontend accessible on Windows 7 with Firefox 115 ESR
- Ensure build transpiles to ES2018+ compatible JavaScript
- Add necessary polyfills for fetch, Promise, and other modern APIs

**Non-Goals:**
- Support Internet Explorer 11 (IE11 support ended for most libraries)
- Support Chrome/Edge on Win7 (both have ended support)
- Modify backend for this change

## Decisions

### 1. Browserslist Configuration
**Decision**: Update package.json browserslist to explicitly include Firefox 115 ESR

```json
"browserslist": {
  "production": [
    ">0.2%",
    "not dead",
    "not op_mini all",
    "firefox >= 115"
  ],
  "development": [
    "last 1 firefox version"
  ]
}
```

**Rationale**: react-scripts uses browserslist to configure Babel and Autoprefixer. Including Firefox 115 ensures code is transpiled to ES2018+ compatible output.

### 2. Polyfill Strategy
**Decision**: Add core-js and whatwg-fetch polyfills

**Alternatives Considered**:
- Using react-app-polyfill (deprecated in CRA 5.x) → Not maintained
- Using babel-polyfill (deprecated) → Use core-js instead

**Rationale**: Firefox 115 ESR lacks some modern APIs like `fetch` is fully supported but `AbortController`, `URL.createObjectURL` may need polyfills. Using core-js ensures broader compatibility.

### 3. UI Library Compatibility
**Decision**: Test Ant Design and MUI with updated browserslist

**Rationale**: Both Ant Design 5.x and MUI 5.x claim Firefox 115 support. The browserslist change should handle CSS autoprefixing. Will verify through testing.

## Risks / Trade-offs

- **[Risk]** Build size increase → Transpiling to older targets increases bundle size
  - **Mitigation**: This is acceptable for Win7 compatibility; modern browsers still get smaller bundles due to browserslist
- **[Risk]** UI library CSS features not supported → Some modern CSS may not work
  - **Mitigation**: Both AntD and MUI support Firefox 115; will test thoroughly
- **[Risk]** Polyfill overhead → Additional JavaScript for older API support
  - **Mitigation**: Only include necessary polyfills, not full core-js

## Migration Plan

1. Modify `package.json` browserslist
2. Install core-js and whatwg-fetch dependencies
3. Create `src/index.js` polyfill imports
4. Rebuild and test in Firefox 115 ESR (or simulate via browserslist)
5. Deploy updated build
