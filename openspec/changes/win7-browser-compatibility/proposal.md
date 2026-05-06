## Why

The OmniDesk application needs to support Windows 7 users. Windows 7's highest supported browser is Firefox 115 ESR (until August 2026), while the current frontend is built with React 18 and modern UI libraries (Ant Design 5.x, MUI 5.x) targeting modern browsers only. Without compatibility modifications, the application will fail to display properly or at all on Win7 browsers.

## What Changes

1. **Update browserslist configuration** in `package.json` to target Firefox 115 ESR
2. **Add required polyfills** for modern JavaScript features not supported by Firefox 115 ESR
3. **Configure Create React App** (react-scripts) to transpile code for older browsers
4. **Review and update UI library configurations** to ensure compatibility with Firefox 115 ESR
5. **Test build output** to verify compatibility across supported browsers

## Capabilities

### New Capabilities
- `win7-browser-support`: Configure frontend build to support Windows 7 browsers (Firefox 115 ESR)

### Modified Capabilities
- None (this is a new capability for the frontend build system)

## Impact

- **Frontend Build**: Modified `package.json` browserslist and added polyfills
- **Dependencies**: May need to add polyfill packages (core-js, whatwg-fetch)
- **Build Output**: Different transpilation output targeting older browsers
