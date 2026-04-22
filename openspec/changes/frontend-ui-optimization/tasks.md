## 1. Theme Configuration

- [ ] 1.1 Extend CSS variables in global.css (add missing variables)
- [ ] 1.2 Create ThemeProvider component in src/shared/components/ui/ThemeProvider.jsx
- [ ] 1.3 Integrate ThemeProvider in src/index.js
- [ ] 1.4 Verify Ant Design components use theme colors

## 2. Route Lazy Loading

- [ ] 2.1 Analyze current routes in src/routes/index.js
- [ ] 2.2 Convert static imports to React.lazy for non-critical routes
- [ ] 2.3 Add Suspense wrapper with loading fallback
- [ ] 2.4 Test all routes work correctly after lazy loading
- [ ] 2.5 Run build and verify multiple chunks generated

## 3. Shared Layout Components

- [ ] 3.1 Create PageLayout component in src/shared/components/ui/PageLayout.jsx
- [ ] 3.2 Create CardContainer component in src/shared/components/ui/CardContainer.jsx
- [ ] 3.3 Create index.js exporting all ui components
- [ ] 3.4 Migrate one sample page to use shared components
- [ ] 3.5 Verify visual consistency with original

## 4. Skeleton Loading

- [ ] 4.1 Create SkeletonTable component in src/shared/components/ui/SkeletonTable.jsx
- [ ] 4.2 Create SkeletonCard component in src/shared/components/ui/SkeletonCard.jsx
- [ ] 4.3 Integrate with React Query loading states
- [ ] 4.4 Test skeleton displays during data fetch

## 5. Validation

- [ ] 5.1 Run npm run lint and fix any issues
- [ ] 5.2 Run npm run build and verify success
- [ ] 5.3 Run npm test and verify all pass
- [ ] 5.4 Manual UI testing across key pages