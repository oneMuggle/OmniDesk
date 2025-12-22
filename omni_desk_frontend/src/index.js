import ReactDOM from 'react-dom/client';

// 第三方库导入
import dayjs from 'dayjs';
import utc from 'dayjs-plugin-utc';
// import timezone from 'dayjs/plugin/timezone'; // 禁用时区插件，用于排查问题
import 'dayjs/locale/zh-cn'; // 导入中文语言包
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ConfigProvider } from 'antd';
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

// dayjs 全局配置
dayjs.extend(utc);
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

const queryClient = new QueryClient();

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ConfigProvider
      modal={{
        getContainer: () => document.getElementById('modal-root'),
        zIndexBase: 1000
      }}
    >
      <ApiProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </ApiProvider>
    </ConfigProvider>
  </React.StrictMode>
);

