module.exports = {
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.[jt]sx?$': 'babel-jest',
  },
  transformIgnorePatterns: [
    "/node_modules/(?!axios|antd|@ant-design|rc-pagination|rc-picker|rc-util|@babel|@emotion)"
  ],
  testTimeout: 60000,
  moduleNameMapper: {
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
    "axios": "axios/dist/node/axios.cjs"
  }
};
