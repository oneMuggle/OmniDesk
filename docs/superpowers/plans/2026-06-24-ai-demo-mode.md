# AI 能力演示模式 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有 Dify/RAGFlow 接入页面在没有真实后端服务时仍能完整跑通核心流程，并新增 `/ai-showcase` 入口页。

**Architecture:** 通过 axios 请求拦截器在 demo 模式下返回 mock 数据，现有业务页面无需修改。新增 DemoContext 全局状态 + DemoToggle 运行时开关 + AIShowcasePage 展示入口页。

**Tech Stack:** React 18 + Axios + Ant Design 5 + Vite + Jest

## Global Constraints

- 不修改后端任何代码
- 不引入 MSW 等重量级 mock 框架
- 纯前端 axios 拦截器实现
- 运行时 toggle + localStorage 持久化
- Dify 官方 demo URL + 前端预置问答表
- 拦截器 URL 模式匹配，未命中透传
- 与现有 refresh-token 拦截器共存（先 mock 后 refresh-token）

---

## Task 1: DemoContext + useDemoMode hook

**Files:**
- Create: `omni_desk_frontend/src/shared/context/DemoContext.jsx`
- Test: `omni_desk_frontend/src/shared/context/__tests__/DemoContext.test.jsx`

**Interfaces:**
- Consumes: 无
- Produces: `DemoProvider`, `useDemoMode()` hook

**Context:**
DemoContext 提供全局 demo 模式开关，状态持久化到 localStorage。遵循 ThemeContext 的实现模式（参考 `src/shared/context/ThemeContext.jsx`）。

---

- [ ] **Step 1: 编写失败测试**

创建 `omni_desk_frontend/src/shared/context/__tests__/DemoContext.test.jsx`:

```jsx
import { render, screen, act } from '@testing-library/react';
import { DemoProvider, useDemoMode } from '../DemoContext';

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => { store[key] = value; }),
    removeItem: jest.fn((key) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('DemoContext', () => {
  beforeEach(() => {
    localStorageMock.clear();
    jest.clearAllMocks();
  });

  const TestComponent = () => {
    const { isDemoMode, setDemoMode } = useDemoMode();
    return (
      <div>
        <span data-testid="mode">{isDemoMode ? 'demo' : 'real'}</span>
        <button onClick={() => setDemoMode(!isDemoMode)}>Toggle</button>
      </div>
    );
  };

  it('默认 isDemoMode 为 false', () => {
    render(
      <DemoProvider>
        <TestComponent />
      </DemoProvider>
    );
    expect(screen.getByTestId('mode').textContent).toBe('real');
  });

  it('切换 demo 模式后更新状态', () => {
    render(
      <DemoProvider>
        <TestComponent />
      </DemoProvider>
    );
    act(() => {
      screen.getByText('Toggle').click();
    });
    expect(screen.getByTestId('mode').textContent).toBe('demo');
  });

  it('切换后写入 localStorage', () => {
    render(
      <DemoProvider>
        <TestComponent />
      </DemoProvider>
    );
    act(() => {
      screen.getByText('Toggle').click();
    });
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'omnidesk:demo-mode',
      'true'
    );
  });

  it('从 localStorage 恢复状态', () => {
    localStorageMock.getItem.mockReturnValue('true');
    render(
      <DemoProvider>
        <TestComponent />
      </DemoProvider>
    );
    expect(screen.getByTestId('mode').textContent).toBe('demo');
  });

  it('localStorage 不可用时回退到内存状态', () => {
    localStorageMock.setItem.mockImplementation(() => { throw new Error('quota'); });
    render(
      <DemoProvider>
        <TestComponent />
      </DemoProvider>
    );
    act(() => {
      screen.getByText('Toggle').click();
    });
    // 不抛出错误，状态仍更新到内存
    expect(screen.getByTestId('mode').textContent).toBe('demo');
  });
});
```

---

- [ ] **Step 2: 运行测试验证失败**

```bash
cd omni_desk_frontend
npm test -- src/shared/context/__tests__/DemoContext.test.jsx --passWithNoTests
```

Expected: FAIL（模块不存在）

---

- [ ] **Step 3: 实现 DemoContext**

创建 `omni_desk_frontend/src/shared/context/DemoContext.jsx`:

```jsx
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';

const STORAGE_KEY = 'omnidesk:demo-mode';

const DemoContext = createContext(null);

export function DemoProvider({ children }) {
  const [isDemoMode, setIsDemoMode] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isDemoMode));
    } catch {
      // localStorage 不可用，忽略
    }
  }, [isDemoMode]);

  const setDemoMode = useCallback((value) => {
    setIsDemoMode(value);
  }, []);

  const value = {
    isDemoMode,
    setDemoMode,
  };

  return (
    <DemoContext.Provider value={value}>
      {children}
    </DemoContext.Provider>
  );
}

export function useDemoMode() {
  const context = useContext(DemoContext);
  if (!context) {
    throw new Error('useDemoMode must be used within a DemoProvider');
  }
  return context;
}

DemoProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
```

---

- [ ] **Step 4: 运行测试验证通过**

```bash
cd omni_desk_frontend
npm test -- src/shared/context/__tests__/DemoContext.test.jsx
```

Expected: PASS

---

- [ ] **Step 5: 提交**

```bash
cd omni_desk_frontend
git add src/shared/context/DemoContext.jsx src/shared/context/__tests__/DemoContext.test.jsx
git commit -m "feat: add DemoContext for AI demo mode toggle"
```

---

## Task 2: Mock 数据文件

**Files:**
- Create: `omni_desk_frontend/src/shared/api/demoMocks.js`

**Interfaces:**
- Consumes: 无
- Produces: `MOCK_DIFY_APPS`, `MOCK_RAGFLOW_CONFIGS`, `MOCK_RAGFLOW_RESPONSES`

**Context:**
提供演示模式下的静态 mock 数据。包含 3 个 Dify 应用（使用真实 demo URL）和 1 个 RAGFlow 配置 + 关键词问答表。

---

- [ ] **Step 1: 创建 demoMocks.js**

创建 `omni_desk_frontend/src/shared/api/demoMocks.js`:

```javascript
/**
 * Demo mode mock data for AI showcase features
 */

export const MOCK_DIFY_APPS = [
  {
    id: 1,
    name: '智能客服助手',
    description: '面向客户的 7×24 智能问答机器人，支持多轮对话与知识库检索',
    embed_url: 'https://udify.app/chatbot/gXvY6jZ9Q5kL3mN',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 2,
    name: '合同审查助手',
    description: '法务合同要点提取与风险标注，自动识别关键条款',
    embed_url: 'https://udify.app/chatbot/aB3cD5eF7gH9iJ',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 3,
    name: '员工手册问答',
    description: 'HR 政策智能检索，快速查询公司规章制度',
    embed_url: 'https://udify.app/chatbot/kL1mN3oP5qR7sT',
    is_active: false,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
];

export const MOCK_RAGFLOW_CONFIGS = [
  {
    id: 1,
    name: '企业知识库（演示）',
    api_endpoint: 'http://demo.ragflow.local',
    api_key: 'demo-key-masked',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 2,
    name: '产品文档库（演示）',
    api_endpoint: 'http://demo.ragflow.local',
    api_key: 'demo-key-masked',
    is_active: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
];

/**
 * 关键词 → 回答的映射表
 * 支持 10+ 条常见问题，未匹配时返回默认回答
 */
export const MOCK_RAGFLOW_RESPONSES = {
  '年假': '根据《员工手册》第 5.2 条：在公司连续工作满 1 年不满 10 年的，年休假 5 天；满 10 年不满 20 年的，年休假 10 天；满 20 年的，年休假 15 天。年假需提前 3 个工作日申请。',
  '报销': '差旅报销标准：\n- 交通：飞机经济舱、高铁二等座\n- 住宿：一线城市 500 元/晚，二线城市 400 元/晚\n- 伙食补助：100 元/天\n\n报销需在出差结束后 7 个工作日内提交，附上发票原件。',
  '加班': '加班需提前申请并经主管批准。加班补偿方式：\n- 工作日加班：1.5 倍工资或调休\n- 周末加班：2 倍工资或调休\n- 法定节假日：3 倍工资（不可调休）\n\n加班申请需在企业微信提交，并附上打卡记录。',
  '试用期': '试用期为 3 个月（特殊岗位可协商延长至 6 个月）。试用期工资为正式工资的 80%。试用期内享受正式员工同等福利（年假按实际工作月份折算）。',
  '转正': '转正流程：\n1. 试用期结束前 2 周，主管发起转正评估\n2. 员工填写转正自评表\n3. 主管填写评估意见\n4. HR 审核并通知结果\n\n转正后享受完整薪资福利。',
  '晋升': '公司每年 4 月和 10 月进行两次晋升窗口。晋升条件：\n- 在当前职级满 1 年以上\n- 最近两次绩效评估为 B 及以上\n- 无重大违纪记录\n\n晋升需提交申请并经晋升委员会评审。',
  '绩效': '绩效评估每季度进行一次（Q1/Q2/Q3/Q4），采用 OKR + 360 度评估。评级分为 S/A/B/C/D 五档：\n- S（卓越）：不超过 10%\n- A（优秀）：不超过 20%\n- B（良好）：约 50%\n- C（待改进）：约 15%\n- D（不合格）：不超过 5%',
  '社保': '公司按国家规定缴纳五险一金：\n- 养老保险：企业 16%，个人 8%\n- 医疗保险：企业 10%，个人 2%\n- 失业保险：企业 0.5%，个人 0.5%\n- 工伤保险：企业 0.4%，个人 0%\n- 生育保险：企业 0.8%，个人 0%\n- 住房公积金：企业 12%，个人 12%',
  '请假': '请假类型及额度：\n- 病假：每年累计不超过 3 个月\n- 事假：需提前申请，无薪\n- 婚假：法定 3 天，晚婚 10 天\n- 产假：女员工 158 天，男员工陪产假 15 天\n- 丧假：直系亲属 3 天\n\n请假需通过 OA 系统申请并附上相关证明。',
  '培训': '公司提供多种培训资源：\n- 内部培训：每月 1-2 次技术分享\n- 外部培训：可申请预算参加行业会议/课程\n- 在线学习：企业账号访问 Coursera/Udemy\n- 导师制度：新员工配备 1 对 1 导师\n\n培训费用报销需提前审批。',
  '__default__': '（演示模式）当前问题未在知识库中匹配到答案。生产环境将基于 RAGFlow 检索返回更精准的回答。您可以尝试其他关键词，或联系管理员补充知识库内容。',
};

/**
 * 根据问题内容匹配回答
 * @param {string} question - 用户问题
 * @returns {string} - 匹配的回答
 */
export function pickMockResponse(question) {
  if (!question || typeof question !== 'string') {
    return MOCK_RAGFLOW_RESPONSES['__default__'];
  }

  const lowerQuestion = question.toLowerCase();

  // 关键词匹配（按优先级排序）
  const keywords = Object.keys(MOCK_RAGFLOW_RESPONSES).filter(k => k !== '__default__');

  for (const keyword of keywords) {
    if (lowerQuestion.includes(keyword.toLowerCase())) {
      return MOCK_RAGFLOW_RESPONSES[keyword];
    }
  }

  return MOCK_RAGFLOW_RESPONSES['__default__'];
}
```

---

- [ ] **Step 2: 提交**

```bash
cd omni_desk_frontend
git add src/shared/api/demoMocks.js
git commit -m "feat: add mock data for AI demo mode"
```

---

## Task 3: Demo 拦截器 + 单元测试

**Files:**
- Create: `omni_desk_frontend/src/shared/api/demoInterceptor.js`
- Test: `omni_desk_frontend/src/shared/api/__tests__/demoInterceptor.test.js`

**Interfaces:**
- Consumes: `MOCK_DIFY_APPS`, `MOCK_RAGFLOW_CONFIGS`, `pickMockResponse` (from Task 2), `useDemoMode` (from Task 1)
- Produces: `setupDemoInterceptor(axiosInstance, getIsDemoMode)`

**Context:**
axios 请求拦截器，在 demo 模式下根据 URL 模式返回 mock 数据。未匹配的请求透传。

---

- [ ] **Step 1: 编写失败测试**

创建 `omni_desk_frontend/src/shared/api/__tests__/demoInterceptor.test.js`:

```javascript
import axios from 'axios';
import { setupDemoInterceptor } from '../demoInterceptor';
import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS } from '../demoMocks';

// Mock axios
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  })),
}));

describe('setupDemoInterceptor', () => {
  let mockAxios;
  let mockInterceptor;
  let getIsDemoMode;

  beforeEach(() => {
    jest.clearAllMocks();
    mockInterceptor = jest.fn();
    mockAxios = {
      interceptors: {
        request: { use: mockInterceptor },
      },
    };
    getIsDemoMode = jest.fn();
  });

  it('注册拦截器', () => {
    setupDemoInterceptor(mockAxios, getIsDemoMode);
    expect(mockInterceptor).toHaveBeenCalledTimes(1);
    expect(typeof mockInterceptor.mock.calls[0][0]).toBe('function');
  });

  describe('demo 模式开启时', () => {
    let interceptorFn;

    beforeEach(() => {
      getIsDemoMode.mockReturnValue(true);
      setupDemoInterceptor(mockAxios, getIsDemoMode);
      interceptorFn = mockInterceptor.mock.calls[0][0];
    });

    it('拦截 GET /api/dify-apps/ 返回列表', async () => {
      const config = { method: 'get', url: '/api/dify-apps/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({ results: MOCK_DIFY_APPS });
    });

    it('拦截 GET /api/dify-apps/:id/ 返回详情', async () => {
      const config = { method: 'get', url: '/api/dify-apps/1/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual(MOCK_DIFY_APPS[0]);
    });

    it('GET 不存在的 id 返回 404', async () => {
      const config = { method: 'get', url: '/api/dify-apps/999/' };
      const result = await interceptorFn(config);
      expect(result.status).toBe(404);
    });

    it('拦截 POST /api/dify-apps/ 创建', async () => {
      const config = { method: 'post', url: '/api/dify-apps/', data: { name: 'Test' } };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({ name: 'Test', id: expect.any(Number) });
    });

    it('拦截 PUT /api/dify-apps/:id/ 更新', async () => {
      const config = { method: 'put', url: '/api/dify-apps/1/', data: { name: 'Updated' } };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({ id: 1, name: 'Updated' });
    });

    it('拦截 DELETE /api/dify-apps/:id/ 删除', async () => {
      const config = { method: 'delete', url: '/api/dify-apps/1/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({});
    });

    it('拦截 GET /api/ragflow-service/configs/ 返回列表', async () => {
      const config = { method: 'get', url: '/api/ragflow-service/configs/' };
      const result = await interceptorFn(config);
      expect(result.data).toEqual({ results: MOCK_RAGFLOW_CONFIGS });
    });

    it('拦截 POST /api/ragflow-service/configs/:id/query/ 返回问答', async () => {
      const config = {
        method: 'post',
        url: '/api/ragflow-service/configs/1/query/',
        data: { question: '年假有多少天？' },
      };
      const result = await interceptorFn(config);
      expect(result.data).toMatchObject({
        answer: expect.stringContaining('员工手册'),
        conversation_id: expect.stringMatching(/^demo-conv-/),
      });
    });

    it('未匹配的 URL 透传', async () => {
      const config = { method: 'get', url: '/api/other-endpoint/' };
      const result = await interceptorFn(config);
      expect(result).toBe(config);
    });
  });

  describe('demo 模式关闭时', () => {
    let interceptorFn;

    beforeEach(() => {
      getIsDemoMode.mockReturnValue(false);
      setupDemoInterceptor(mockAxios, getIsDemoMode);
      interceptorFn = mockInterceptor.mock.calls[0][0];
    });

    it('所有请求透传', async () => {
      const config = { method: 'get', url: '/api/dify-apps/' };
      const result = await interceptorFn(config);
      expect(result).toBe(config);
    });
  });
});
```

---

- [ ] **Step 2: 运行测试验证失败**

```bash
cd omni_desk_frontend
npm test -- src/shared/api/__tests__/demoInterceptor.test.js
```

Expected: FAIL（模块不存在）

---

- [ ] **Step 3: 实现 demoInterceptor**

创建 `omni_desk_frontend/src/shared/api/demoInterceptor.js`:

```javascript
import { MOCK_DIFY_APPS, MOCK_RAGFLOW_CONFIGS, pickMockResponse } from './demoMocks';
import { logger } from '../utils/logger';

/**
 * 设置 demo 模式拦截器
 * @param {import('axios').AxiosInstance} axiosInstance - axios 实例
 * @param {() => boolean} getIsDemoMode - 获取当前 demo 模式的函数
 */
export function setupDemoInterceptor(axiosInstance, getIsDemoMode) {
  axiosInstance.interceptors.request.use(async (config) => {
    if (!getIsDemoMode()) {
      return config;
    }

    const { method, url } = config;

    // GET /api/dify-apps/
    if (method === 'get' && /^\/api\/dify-apps\/?$/.test(url)) {
      logger.debug('[demo] intercepted GET /api/dify-apps/');
      return Promise.resolve({ data: { results: MOCK_DIFY_APPS }, status: 200, config });
    }

    // GET /api/dify-apps/:id/
    const difyDetailMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (method === 'get' && difyDetailMatch) {
      const id = parseInt(difyDetailMatch[1], 10);
      const app = MOCK_DIFY_APPS.find(a => a.id === id);
      if (app) {
        logger.debug('[demo] intercepted GET /api/dify-apps/:id/', { id });
        return Promise.resolve({ data: app, status: 200, config });
      }
      return Promise.resolve({ data: { detail: 'Not found' }, status: 404, config });
    }

    // POST /api/dify-apps/
    if (method === 'post' && /^\/api\/dify-apps\/?$/.test(url)) {
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const newApp = {
        ...payload,
        id: Date.now(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      logger.debug('[demo] intercepted POST /api/dify-apps/', { newApp });
      return Promise.resolve({ data: newApp, status: 201, config });
    }

    // PUT /api/dify-apps/:id/
    const difyUpdateMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (method === 'put' && difyUpdateMatch) {
      const id = parseInt(difyUpdateMatch[1], 10);
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const existing = MOCK_DIFY_APPS.find(a => a.id === id);
      const updated = { ...existing, ...payload, id };
      logger.debug('[demo] intercepted PUT /api/dify-apps/:id/', { id, updated });
      return Promise.resolve({ data: updated, status: 200, config });
    }

    // DELETE /api/dify-apps/:id/
    const difyDeleteMatch = url.match(/^\/api\/dify-apps\/(\d+)\/?$/);
    if (method === 'delete' && difyDeleteMatch) {
      const id = parseInt(difyDeleteMatch[1], 10);
      logger.debug('[demo] intercepted DELETE /api/dify-apps/:id/', { id });
      return Promise.resolve({ data: {}, status: 204, config });
    }

    // GET /api/ragflow-service/configs/
    if (method === 'get' && /^\/api\/ragflow-service\/configs\/?$/.test(url)) {
      logger.debug('[demo] intercepted GET /api/ragflow-service/configs/');
      return Promise.resolve({ data: { results: MOCK_RAGFLOW_CONFIGS }, status: 200, config });
    }

    // POST /api/ragflow-service/configs/:id/query/
    const ragflowQueryMatch = url.match(/^\/api\/ragflow-service\/configs\/(\d+)\/query\/?$/);
    if (method === 'post' && ragflowQueryMatch) {
      const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
      const answer = pickMockResponse(payload.question);
      logger.debug('[demo] intercepted POST /api/ragflow-service/configs/:id/query/', { question: payload.question });
      return Promise.resolve({
        data: {
          answer,
          conversation_id: `demo-conv-${Date.now()}`,
        },
        status: 200,
        config,
      });
    }

    // 未匹配，透传
    return config;
  });
}
```

---

- [ ] **Step 4: 运行测试验证通过**

```bash
cd omni_desk_frontend
npm test -- src/shared/api/__tests__/demoInterceptor.test.js
```

Expected: PASS

---

- [ ] **Step 5: 提交**

```bash
cd omni_desk_frontend
git add src/shared/api/demoInterceptor.js src/shared/api/__tests__/demoInterceptor.test.js
git commit -m "feat: add demo mode axios interceptor"
```

---

## Task 4: 注册拦截器到 axiosConfig

**Files:**
- Modify: `omni_desk_frontend/src/shared/api/axiosConfig.ts`

**Interfaces:**
- Consumes: `setupDemoInterceptor` (from Task 3), `useDemoMode` (from Task 1)

**Context:**
在 axiosConfig.ts 末尾注册 demo 拦截器。需要全局访问 demo 模式状态，因此使用模块级变量 + setter。

---

- [ ] **Step 1: 修改 axiosConfig.ts**

在 `omni_desk_frontend/src/shared/api/axiosConfig.ts` 末尾（`export default instance;` 之前）添加：

```typescript
// Demo mode interceptor setup
let isDemoModeGlobal = false;

export function setDemoModeEnabled(enabled: boolean): void {
    isDemoModeGlobal = enabled;
}

import { setupDemoInterceptor } from './demoInterceptor';
setupDemoInterceptor(instance, () => isDemoModeGlobal);
```

---

- [ ] **Step 2: 提交**

```bash
cd omni_desk_frontend
git add src/shared/api/axiosConfig.ts
git commit -m "feat: register demo interceptor in axiosConfig"
```

---

## Task 5: DemoToggle 组件

**Files:**
- Create: `omni_desk_frontend/src/shared/components/DemoToggle.jsx`
- Test: `omni_desk_frontend/src/shared/components/__tests__/DemoToggle.test.jsx`

**Interfaces:**
- Consumes: `useDemoMode` (from Task 1), `setDemoModeEnabled` (from Task 4)

**Context:**
顶部 toggle 组件，切换 demo 模式并同步到全局 axios 拦截器。使用 Ant Design Switch。

---

- [ ] **Step 1: 编写失败测试**

创建 `omni_desk_frontend/src/shared/components/__tests__/DemoToggle.test.jsx`:

```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { DemoProvider } from '../../context/DemoContext';
import DemoToggle from '../DemoToggle';

// Mock setDemoModeEnabled
jest.mock('../../api/axiosConfig', () => ({
  setDemoModeEnabled: jest.fn(),
}));

describe('DemoToggle', () => {
  it('渲染开关', () => {
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('切换时调用 setDemoModeEnabled', () => {
    const { setDemoModeEnabled } = require('../../api/axiosConfig');
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    fireEvent.click(screen.getByRole('switch'));
    expect(setDemoModeEnabled).toHaveBeenCalledWith(true);
  });

  it('显示当前模式文本', () => {
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    expect(screen.getByText(/演示模式/)).toBeInTheDocument();
  });
});
```

---

- [ ] **Step 2: 运行测试验证失败**

```bash
cd omni_desk_frontend
npm test -- src/shared/components/__tests__/DemoToggle.test.jsx
```

Expected: FAIL

---

- [ ] **Step 3: 实现 DemoToggle**

创建 `omni_desk_frontend/src/shared/components/DemoToggle.jsx`:

```jsx
import { Switch, Space, message } from 'antd';
import { useDemoMode } from '../context/DemoContext';
import { setDemoModeEnabled } from '../api/axiosConfig';

const DemoToggle = () => {
  const { isDemoMode, setDemoMode } = useDemoMode();

  const handleChange = (checked) => {
    setDemoMode(checked);
    setDemoModeEnabled(checked);
    message.success(checked ? '已切换到演示模式' : '已切换到真实模式');
  };

  return (
    <Space>
      <span style={{ fontSize: 12, color: '#666' }}>演示模式</span>
      <Switch
        size="small"
        checked={isDemoMode}
        onChange={handleChange}
      />
    </Space>
  );
};

export default DemoToggle;
```

---

- [ ] **Step 4: 运行测试验证通过**

```bash
cd omni_desk_frontend
npm test -- src/shared/components/__tests__/DemoToggle.test.jsx
```

Expected: PASS

---

- [ ] **Step 5: 提交**

```bash
cd omni_desk_frontend
git add src/shared/components/DemoToggle.jsx src/shared/components/__tests__/DemoToggle.test.jsx
git commit -m "feat: add DemoToggle component"
```

---

## Task 6: 嵌入 DemoToggle 到 App

**Files:**
- Modify: `omni_desk_frontend/src/App.jsx`

**Interfaces:**
- Consumes: `DemoProvider` (from Task 1), `DemoToggle` (from Task 5)

**Context:**
在 App.jsx 中包裹 DemoProvider 并在 Sidebar 中嵌入 DemoToggle。

---

- [ ] **Step 1: 修改 App.jsx 添加 DemoProvider**

在 `omni_desk_frontend/src/App.jsx` 顶部添加 import：

```jsx
import { DemoProvider } from './shared/context/DemoContext';
import { setDemoModeEnabled } from './shared/api/axiosConfig';
```

在 `<ThemeProvider>` 内部添加 `<DemoProvider>`：

```jsx
<ThemeProvider>
  <DemoProvider>
    <ThemeAwareConfigProvider>
      ...
    </ThemeAwareConfigProvider>
  </DemoProvider>
</ThemeProvider>
```

---

- [ ] **Step 2: 修改 Sidebar.jsx 嵌入 DemoToggle**

在 `omni_desk_frontend/src/shared/components/Sidebar.jsx` 顶部添加 import：

```jsx
import DemoToggle from './DemoToggle';
```

在 Sidebar 组件的顶部区域（如 ThemeSelector 旁边）添加：

```jsx
<DemoToggle />
```

---

- [ ] **Step 3: 提交**

```bash
cd omni_desk_frontend
git add src/App.jsx src/shared/components/Sidebar.jsx
git commit -m "feat: integrate DemoProvider and DemoToggle into app"
```

---

## Task 7: AIShowcasePage + CSS

**Files:**
- Create: `omni_desk_frontend/src/shared/pages/AIShowcasePage.jsx`
- Create: `omni_desk_frontend/src/shared/pages/AIShowcasePage.css`
- Test: `omni_desk_frontend/src/shared/pages/__tests__/AIShowcasePage.test.jsx`

**Interfaces:**
- Consumes: 无（静态展示页）

**Context:**
集中展示 Dify 和 RAGFlow 能力的入口页。左侧 Dify 卡片，右侧 RAGFlow 卡片，点击"立即体验"跳转到对应页面。

---

- [ ] **Step 1: 编写失败测试**

创建 `omni_desk_frontend/src/shared/pages/__tests__/AIShowcasePage.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIShowcasePage from '../AIShowcasePage';

describe('AIShowcasePage', () => {
  it('渲染页面标题', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText(/AI 能力展示/)).toBeInTheDocument();
  });

  it('渲染 Dify 卡片', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText(/Dify/)).toBeInTheDocument();
  });

  it('渲染 RAGFlow 卡片', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText(/RAGFlow|Ragflow/)).toBeInTheDocument();
  });

  it('包含"立即体验"按钮', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const buttons = screen.getAllByText(/立即体验/);
    expect(buttons.length).toBeGreaterThanOrEqual(2);
  });
});
```

---

- [ ] **Step 2: 运行测试验证失败**

```bash
cd omni_desk_frontend
npm test -- src/shared/pages/__tests__/AIShowcasePage.test.jsx
```

Expected: FAIL

---

- [ ] **Step 3: 实现 AIShowcasePage**

创建 `omni_desk_frontend/src/shared/pages/AIShowcasePage.jsx`:

```jsx
import { Card, Button, Row, Col, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { RobotOutlined, ExperimentOutlined } from '@ant-design/icons';
import './AIShowcasePage.css';

const { Title, Paragraph } = Typography;

const AIShowcasePage = () => {
  const navigate = useNavigate();

  return (
    <div className="ai-showcase-page">
      <div className="showcase-header">
        <Title level={2}>AI 能力展示</Title>
        <Paragraph>
          OmniDesk 集成了 Dify 和 RAGFlow 两大 AI 平台，为企业提供智能问答、知识库检索等能力。
        </Paragraph>
      </div>

      <Row gutter={[24, 24]} justify="center">
        <Col xs={24} md={12} lg={10}>
          <Card
            className="showcase-card"
            hoverable
            cover={
              <div className="card-icon dify">
                <RobotOutlined style={{ fontSize: 64, color: '#1890ff' }} />
              </div>
            }
          >
            <Card.Meta
              title="Dify 智能应用"
              description="快速构建 AI 应用，支持多轮对话、知识库集成、工作流编排"
            />
            <div className="card-features">
              <ul>
                <li>智能客服助手</li>
                <li>合同审查工具</li>
                <li>员工手册问答</li>
              </ul>
            </div>
            <Button
              type="primary"
              block
              onClick={() => navigate('/dify-apps')}
              style={{ marginTop: 16 }}
            >
              立即体验 →
            </Button>
          </Card>
        </Col>

        <Col xs={24} md={12} lg={10}>
          <Card
            className="showcase-card"
            hoverable
            cover={
              <div className="card-icon ragflow">
                <ExperimentOutlined style={{ fontSize: 64, color: '#52c41a' }} />
              </div>
            }
          >
            <Card.Meta
              title="RAGFlow 知识检索"
              description="基于 RAG 的企业知识库问答，精准检索与智能回答"
            />
            <div className="card-features">
              <ul>
                <li>企业知识库问答</li>
                <li>产品文档检索</li>
                <li>多轮对话支持</li>
              </ul>
            </div>
            <Button
              type="primary"
              block
              onClick={() => navigate('/ragflow-chat')}
              style={{ marginTop: 16 }}
            >
              立即体验 →
            </Button>
          </Card>
        </Col>
      </Row>

      <div className="showcase-footer">
        <Paragraph type="secondary">
          💡 提示：开启右上角"演示模式"可在无后端服务时体验完整流程
        </Paragraph>
      </div>
    </div>
  );
};

export default AIShowcasePage;
```

---

- [ ] **Step 4: 创建 CSS**

创建 `omni_desk_frontend/src/shared/pages/AIShowcasePage.css`:

```css
.ai-showcase-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.showcase-header {
  text-align: center;
  margin-bottom: 48px;
}

.showcase-header h2 {
  margin-bottom: 16px;
}

.showcase-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 180px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%);
}

.card-icon.ragflow {
  background: linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%);
}

.card-features {
  margin-top: 16px;
}

.card-features ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.card-features li {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.card-features li:last-child {
  border-bottom: none;
}

.card-features li::before {
  content: '✓';
  color: #52c41a;
  font-weight: bold;
  margin-right: 8px;
}

.showcase-footer {
  text-align: center;
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid #f0f0f0;
}
```

---

- [ ] **Step 5: 运行测试验证通过**

```bash
cd omni_desk_frontend
npm test -- src/shared/pages/__tests__/AIShowcasePage.test.jsx
```

Expected: PASS

---

- [ ] **Step 6: 提交**

```bash
cd omni_desk_frontend
git add src/shared/pages/AIShowcasePage.jsx src/shared/pages/AIShowcasePage.css src/shared/pages/__tests__/AIShowcasePage.test.jsx
git commit -m "feat: add AI showcase entry page"
```

---

## Task 8: 注册路由和菜单

**Files:**
- Modify: `omni_desk_frontend/src/routes/index.jsx`
- Modify: `omni_desk_frontend/src/shared/config/menuConfig.jsx`

**Interfaces:**
- Consumes: `AIShowcasePage` (from Task 7)

**Context:**
在路由和侧边栏菜单中添加 `/ai-showcase` 入口。

---

- [ ] **Step 1: 修改 routes/index.jsx**

在 `omni_desk_frontend/src/routes/index.jsx` 顶部添加 lazy import：

```jsx
const AIShowcasePage = lazy(() => import('../shared/pages/AIShowcasePage'));
```

在路由配置中添加（建议放在 AI 助手子菜单附近）：

```jsx
{
  path: "ai-showcase",
  element: <ProtectedRoute pageName="AI能力展示"><LazyComponent component={AIShowcasePage} /></ProtectedRoute>
},
```

---

- [ ] **Step 2: 修改 menuConfig.jsx**

在 `omni_desk_frontend/src/shared/config/menuConfig.jsx` 的 AI 助手子菜单中添加：

```jsx
{ to: "/ai-showcase", icon: AppstoreOutlined, text: "AI 能力展示", permission: null },
```

（放在子菜单的第一项）

---

- [ ] **Step 3: 运行全部测试**

```bash
cd omni_desk_frontend
npm test
```

Expected: PASS

---

- [ ] **Step 4: 提交**

```bash
cd omni_desk_frontend
git add src/routes/index.jsx src/shared/config/menuConfig.jsx
git commit -m "feat: add ai-showcase route and menu entry"
```

---

## Task 9: 验证覆盖率

**Files:**
- 无新文件

**Context:**
运行测试覆盖率报告，验证达到 80% 目标。

---

- [ ] **Step 1: 运行覆盖率**

```bash
cd omni_desk_frontend
npm run test:coverage -- --coveragePathIgnorePatterns="node_modules"
```

Expected: 新增文件覆盖率 ≥ 80%

---

- [ ] **Step 2: 检查报告**

如果覆盖率不足，补充测试用例。

---

- [ ] **Step 3: 提交（如有新增测试）**

```bash
cd omni_desk_frontend
git add src/**/__tests__/*.test.*
git commit -m "test: improve coverage for demo mode features"
```

---

## Task 10: E2E 测试（可选）

**Files:**
- Create: `omni_desk_frontend/e2e/ai-demo-mode.spec.js`

**Context:**
使用 Playwright 验证完整 demo 流程。

---

- [ ] **Step 1: 创建 E2E 测试**

创建 `omni_desk_frontend/e2e/ai-demo-mode.spec.js`:

```javascript
import { test, expect } from '@playwright/test';

test.describe('AI Demo Mode', () => {
  test('开启 demo 模式后可以看到 mock 数据', async ({ page }) => {
    await page.goto('/ai-showcase');
    
    // 开启 demo 模式
    await page.getByRole('switch').click();
    
    // 跳转到 Dify 应用页
    await page.click('text=立即体验 →');
    
    // 等待页面加载，验证看到 mock 数据
    await expect(page.getByText('智能客服助手')).toBeVisible();
  });
});
```

---

- [ ] **Step 2: 运行 E2E（需要启动服务）**

```bash
cd omni_desk_frontend
npm run e2e
```

Expected: PASS

---

- [ ] **Step 3: 提交**

```bash
cd omni_desk_frontend
git add e2e/ai-demo-mode.spec.js
git commit -m "test: add E2E test for demo mode"
```

---

## 完成检查清单

- [ ] 所有 Task 1-10 完成
- [ ] 测试全部通过
- [ ] 覆盖率 ≥ 80%
- [ ] 无 TypeScript/ESLint 错误
- [ ] 手动验证：开启 demo 模式 → 访问 `/dify-apps` 看到 mock 数据 → 访问 `/ragflow-chat` 可以提问

---

## 回滚方案

如需回滚，删除以下 commit：
```bash
git revert <commit-hash>  # 从最后一个 commit 开始
```

或整体回滚：
```bash
git reset --hard HEAD~10  # 假设共 10 个 commit
```
