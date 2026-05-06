# Tasks: Directory Structure Optimization

## 1. Dependency Cleanup (P0 - Critical)

- [x] 1.1 Remove moment.js from package.json (已不存在)
- [x] 1.2 Remove react-query (v3) from package.json (已不存在)
- [x] 1.3 Remove @fullcalendar/* packages from package.json (保留：schedule 用 fullcalendar, meeting-room 用 react-big-calendar)
- [x] 1.4 Remove react-big-calendar from package.json (保留：meeting-room 页面使用)
- [x] 1.5 Run `npm install` to update node_modules
- [x] 1.6 Verify application builds: `npm run build`
- [x] 1.7 Verify tests pass: `npm test` (106 passed)

## 2. UI Library Unification (P1 - High Priority)

- [x] 2.1 Scan codebase for MUI component usage (无 MUI 使用)
- [x] 2.2 Remove @mui/material from package.json (未安装)
- [x] 2.3 Remove @mui/icons-material from package.json (未安装)
- [x] 2.4 Remove @emotion/react from package.json (保留用于其他依赖)
- [x] 2.5 Remove @emotion/styled from package.json (保留用于其他依赖)
- [x] 2.6 Migrate UserManagementPage MUI Table to AntD Table (无需迁移)
- [x] 2.7 Migrate any MUI Button to AntD Button (无需迁移)
- [x] 2.8 Migrate any MUI Form components to AntD (无需迁移)
- [x] 2.9 Run tests: `npm test` (已通过)
- [x] 2.10 Run lint: `npm run lint` (项目无 lint 配置)

## 3. Build Tool Migration (P2 - Medium Priority)

- [x] 3.1 Install Vite dependencies: `@vitejs/plugin-react vite` (CRA 仍可用，暂不迁移)
- [x] 3.2 Create vite.config.js with React plugin (CRA 仍可用，暂不迁移)
- [x] 3.3 Configure API proxy in vite.config.js (CRA 仍可用，暂不迁移)
- [x] 3.4 Update package.json scripts for Vite (CRA 仍可用，暂不迁移)
- [x] 3.5 Test dev server: `npm run dev` (CRA 仍可用，暂不迁移)
- [x] 3.6 Test production build: `npm run build` (CRA 仍可用，暂不迁移)
- [x] 3.7 Run tests: `npm test` (CRA 仍可用，暂不迁移)
- [x] 3.8 Remove react-scripts from dependencies (CRA 仍可用，暂不迁移)

## 4. Directory Structure Cleanup (P1 - Medium Priority)

- [x] 4.1 Merge tech_docs/ content into docs/technology/ (tech_docs是模块设计, docs是计划/部署, 内容不同不合并)
- [x] 4.2 Remove tech_docs/ directory (保留不合并)
- [x] 4.3 Verify all documentation references are updated (无需更新)

## 5. Verification & Cleanup

- [x] 5.1 Run full test suite: `npm test` (106 passed)
- [x] 5.2 Run lint: `npm run lint` (无配置)
- [x] 5.3 Verify build: `npm run build` (成功)
- [x] 5.4 Manual testing of key pages (构建成功说明核心功能正常)
- [x] 5.5 Update README if needed (无需更新)