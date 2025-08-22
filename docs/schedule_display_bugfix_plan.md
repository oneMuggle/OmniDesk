# 试验日程界面数据显示 Bug 修复计划

## 1. 问题描述

试验日程界面在初始加载时无法显示已有的试验信息，需要用户手动刷新页面后才能看到数据。

## 2. 问题根源分析

- `TrialScheduleContainer.jsx` 组件负责渲染试验日程日历。
- 该组件通过 `useTrialScheduleData` hook 获取试验数据。
- 当前实现中，组件没有正确处理 `isTrialsLoading` 这个数据加载状态。
- 组件在初次渲染时，数据获取尚未完成，`trialEvents` 数组为空，导致日历显示为空。
- 数据加载完成后，由于组件不依赖于加载状态，因此不会触发重新渲染。

## 3. 修复方案

### 步骤 1: 修改 `omni_desk_frontend/src/components/TrialScheduleContainer.jsx`

- **获取加载状态**：在 `useTrialScheduleData` hook 的解构赋值中，增加 `isTrialsLoading`。
- **添加 `useEffect`**：引入 `useEffect` hook，监听 `isTrialsLoading` 的变化。当它从 `true` 变为 `false` 时，执行 `trialQueryClient.invalidateQueries(['trials'])`，强制刷新 `react-query` 的缓存，确保获取并显示最新数据。
- **条件渲染**：在组件的 JSX 部分，根据 `isTrialsLoading` 的值进行条件渲染。
    - 如果 `isTrialsLoading` 为 `true`，显示一个加载指示器（例如 "Loading..." 或一个 Spinner 组件）。
    - 如果 `isTrialsLoading` 为 `false`，则正常渲染 `<TrialSchedule>` 组件。

### 步骤 2 (可选优化): 修改 `omni_desk_frontend/src/hooks/useTrialScheduleData.js`

- **优化数据重新获取策略**：在 `useQuery` 的配置对象中，添加 `refetchOnWindowFocus: false`。这可以防止在用户切换浏览器标签页或窗口时，不必要地重新触发数据获取请求，从而提升性能和用户体验。

## 4. Mermaid 流程图

```mermaid
graph TD
    A[开始] --> B{分析 TrialScheduleContainer.jsx};
    B --> C{发现未处理 isTrialsLoading};
    C --> D[制定修复计划];
    D --> E{步骤 1: 修改 TrialScheduleContainer.jsx};
    E --> E1[从 useTrialScheduleData 获取 isTrialsLoading];
    E --> E2[添加 useEffect 监听 isTrialsLoading 变化];
    E2 --> E3[在数据加载完成后手动刷新缓存];
    E --> E4[根据 isTrialsLoading 条件渲染];
    E4 --> E4a[加载中: 显示 Loading...];
    E4 --> E4b[加载完成: 显示 TrialSchedule];
    D --> F{步骤 2 (可选): 优化 useTrialScheduleData.js};
    F --> F1[配置 refetchOnWindowFocus 为 false];
    F1 & E4b --> G[完成];