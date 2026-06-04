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
    include: /\.jsx?$/,
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
          vendor: ['react', 'react-dom', 'react-router-dom'],
          antd: ['antd', '@ant-design/icons'],
          fullcalendar: ['@fullcalendar/core', '@fullcalendar/react', '@fullcalendar/daygrid', '@fullcalendar/timegrid', '@fullcalendar/interaction', '@fullcalendar/list'],
        },
      },
    },
  },
});
