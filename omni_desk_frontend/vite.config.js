/* eslint-env node */
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    react({
      include: /\.(jsx|js|tsx|ts)$/,
    }),
  ],
  resolve: {
    alias: {
      src: resolve(__dirname, 'src'),
    },
  },
  server: {
    // host: true 等价于 '0.0.0.0',允许容器外部访问 dev server。
    // 本机直接 `npm run dev` 时仍可通过 localhost:3000 访问。
    host: true,
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/django-static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  esbuild: {
    jsx: 'automatic',
    // 包含 .ts/.tsx:与 refactor/shared-api-typescript 同步开启 TypeScript 编译
    include: /\.(jsx?|tsx?)$/,
  },
  optimizeDeps: {
    esbuildOptions: {
      jsx: 'automatic',
      loader: {
        '.js': 'jsx',
      },
    },
  },
  build: {
    target: 'chrome86',
    outDir: 'build',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // 核心 React 生态(几乎所有页面都依赖)
          vendor: ['react', 'react-dom', 'react-router-dom'],
          // HTTP 客户端(API 调用均依赖)
          http: ['axios'],
          // 时间处理
          datetime: ['dayjs', 'dayjs-plugin-utc', 'date-fns'],
          // 服务端状态管理
          data: ['@tanstack/react-query', '@tanstack/react-query-devtools'],
          // Ant Design 生态
          antd: ['antd', '@ant-design/icons'],
          // 图标库
          icons: ['@fortawesome/fontawesome-svg-core', '@fortawesome/free-solid-svg-icons', '@fortawesome/react-fontawesome'],
          // 拖拽
          dnd: ['@hello-pangea/dnd', 'react-dnd', 'react-dnd-html5-backend'],
          // 富文本编辑器(quill / tiptap 二选一,合并到一个 chunk 避免重复)
          editor: ['react-quill', 'quill', '@tiptap/react', '@tiptap/starter-kit'],
          // 日历
          fullcalendar: ['@fullcalendar/core', '@fullcalendar/react', '@fullcalendar/daygrid', '@fullcalendar/timegrid', '@fullcalendar/interaction', '@fullcalendar/list'],
          // 文档处理(Word/Excel 转 PDF/图片)
          docprocessing: ['docxtemplater', 'mammoth', 'jspdf', 'html2canvas', 'file-saver', 'dompurify'],
          // 通知
          notify: ['react-toastify', 'react-tooltip', 'tippy.js'],
          // Markdown 渲染
          markdown: ['react-markdown', 'remark-gfm'],
          // JWT 解析
          jwt: ['jwt-decode'],
        },
      },
    },
  },
});
