module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  transform: {
    '^.+\\.[jt]sx?$': 'babel-jest',
  },
  transformIgnorePatterns: [
    '/node_modules/(?!(axios|@ant-design|antd|dayjs|@tanstack|react-router|react-router-dom|@babel|d3|@quill|quill|@tiptap|prosemirror-[^/]+|@hello-pangea|@fullcalendar|react-dnd|react-dnd-html5-backend|react-markdown|remark-[^/]+|rehype-[^/]+|unist-[^/]+|vfile|vfile-message|devlop|micromark[^/]*|mdast-[^/]*|hast-[^/]*|trim-lines|property-information|space-separated-tokens|comma-separated-tokens|bail|is-plain-obj|trough|ccount|escape-string-regexp|html-void-elements|stringify-entities|character-entities-html4|decode-named-character-reference|longest-streak|jspdf|raf|dompurify|rgbcolor|stackblur-canvas)(/.|$))',
  ],
  testTimeout: 60000,
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    'axios': 'axios/dist/node/axios.cjs',
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.test.{js,jsx,ts,tsx}',
    '!src/**/index.{js,ts}',
    '!src/reportWebVitals.{js,ts}',
  ],
  coverageReporters: ['html', 'text', 'lcov', 'json'],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  testPathIgnorePatterns: ['/node_modules/'],
  coveragePathIgnorePatterns: ['/node_modules/'],
};
