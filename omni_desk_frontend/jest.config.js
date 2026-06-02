module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  transform: {
    '^.+\\.[jt]sx?$': 'babel-jest',
  },
  transformIgnorePatterns: [
    '/node_modules/(?!(axios|@ant-design|antd|dayjs|@tanstack|react-router|react-router-dom|@babel|d3|@quill|quill|@tiptap|prosemirror-[^/]+|@hello-pangea|@fullcalendar|preact|react-dnd|react-dnd-html5-backend|react-markdown|remark-[^/]+|rehype-[^/]+|unist-[^/]+|vfile|vfile-message|devlop|micromark[^/]*|mdast-[^/]*|hast-[^/]*|trim-lines|property-information|space-separated-tokens|comma-separated-tokens|bail|is-plain-obj|trough|ccount|escape-string-regexp|html-void-elements|stringify-entities|character-entities-html4|decode-named-character-reference|longest-streak|jspdf|raf|dompurify|rgbcolor|stackblur-canvas|moment)(/.|$))',
  ],
  testTimeout: 60000,
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    'axios': 'axios/dist/node/axios.cjs',
    '^jspdf$': '<rootDir>/src/__mocks__/jspdf.js',
    '^html2canvas$': '<rootDir>/src/__mocks__/html2canvas.js',
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.test.{js,jsx,ts,tsx}',
    '!src/**/index.{js,ts}',
    '!src/reportWebVitals.{js,ts}',
  ],
  coverageReporters: ['html', 'text', 'lcov', 'json'],
  // 覆盖率阈值：基于当前实际水平设定基线，逐步提升
  // 当前: statements 23%, branches 19%, lines 24%, functions 23%
  coverageThreshold: {
    global: {
      branches: 19,
      functions: 23,
      lines: 24,
      statements: 23,
    },
  },
  testPathIgnorePatterns: ['/node_modules/'],
  coveragePathIgnorePatterns: ['/node_modules/'],
};
