import 'core-js/stable';
import 'whatwg-fetch';

import ReactDOM from 'react-dom/client';

// 第三方库导入
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isBetween from 'dayjs/plugin/isBetween';
import relativeTime from 'dayjs/plugin/relativeTime';
// import timezone from 'dayjs/plugin/timezone'; // 禁用时区插件，用于排查问题
import 'dayjs/locale/zh-cn'; // 导入中文语言包
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, theme } from 'antd';
import { library, config } from '@fortawesome/fontawesome-svg-core'; // 导入 config
import React from 'react';
import {
  faBold, faItalic, faStrikethrough, faParagraph,
  faHeading, faListUl, faListOl, faQuoteRight, faUndo, faRedo,
  faMagic, faLanguage, faSpellCheck
} from '@fortawesome/free-solid-svg-icons';

// 本地 CSS 文件
import './index.css';
import 'antd/dist/reset.css';
import './shared/styles/global.css';

// 本地模块导入
import router from './routes';
import { AuthProvider } from './features/auth/context/AuthContext';
import { ApiProvider } from './shared/context/ApiProvider';
import { logger } from './shared/utils/logger';

// 注册全局错误监听(部署前 P0-1:浏览器侧错误上报)
// - window.onerror:同步运行时错误(ReferenceError、TypeError 等)
// - window.unhandledrejection:Promise 拒绝未捕获
// 必须在 React 渲染前注册,确保初始化阶段错误也能捕获
window.addEventListener('error', (event) => {
  logger.report({
    kind: 'window.onerror',
    message: event.message || String(event.error),
    stack: (event.error && event.error.stack) || '',
    source: event.filename ? `${event.filename}:${event.lineno}:${event.colno}` : 'window.onerror',
  });
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  logger.report({
    kind: 'unhandledrejection',
    message: (reason && reason.message) || String(reason),
    stack: (reason && reason.stack) || '',
    source: 'unhandledrejection',
  });
});

// dayjs 全局配置
dayjs.extend(utc);
dayjs.extend(weekOfYear);
dayjs.extend(isBetween);
dayjs.extend(relativeTime);
// dayjs.extend(timezone); // 禁用时区插件，用于排查问题
dayjs.locale('zh-cn'); // 设置全局语言为中文
// dayjs.tz.setDefault('Asia/Shanghai'); // 禁用时区设置，用于排查问题

// 禁用 Font Awesome 自动添加 CSS，因为我们手动导入了 styles.css
config.autoAddCss = false;

// 将所有需要使用的 FontAwesome 图标添加到库中
library.add(
  faBold, faItalic, faStrikethrough, faParagraph,
  faHeading, faListUl, faListOl, faQuoteRight, faUndo, faRedo,
  faMagic, faLanguage, faSpellCheck
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      refetchOnWindowFocus: false, // 禁用窗口聚焦时重新获取
      retry: 1, // 重试1次
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 2,
        },
        algorithm: theme.defaultAlgorithm,
      }}
      modal={{
        getContainer: () => document.getElementById('modal-root'),
        zIndexBase: 1000
      }}
    >
      <ApiProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} future={{ v7_startTransition: true }} />
          </AuthProvider>
        </QueryClientProvider>
      </ApiProvider>
    </ConfigProvider>
  </React.StrictMode>
);

