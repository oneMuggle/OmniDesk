import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import { library, config } from '@fortawesome/fontawesome-svg-core'; // 导入 config
import {
  faBold, faItalic, faStrikethrough, faParagraph,
  faHeading, faListUl, faListOl, faQuoteRight, faUndo, faRedo,
  faMagic, faLanguage, faSpellCheck
} from '@fortawesome/free-solid-svg-icons';

import './index.css';
import '@fortawesome/fontawesome-svg-core/styles.css'; // 导入 FontAwesome 核心样式
import 'antd/dist/reset.css';

import router from './routes';
import reportWebVitals from './reportWebVitals';
import { AuthProvider } from './context/AuthContext';
import { ApiProvider } from './context/ApiProvider';

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

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
