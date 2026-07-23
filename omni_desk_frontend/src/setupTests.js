/* eslint-env jest */
// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

window.TextEncoder = TextEncoder;
window.TextDecoder = TextDecoder;

// performance.now() 用于打字机节流等动画逻辑,部分 jsdom 版本未暴露为裸全局变量
if (typeof performance === 'undefined' || typeof performance.now !== 'function') {
  globalThis.performance = { now: () => Date.now() };
}

// Mock matchMedia (Ant Design 5 uses addEventListener/removeEventListener)
window.matchMedia = window.matchMedia || function () {
  return {
    matches: false,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  };
};

window.Notification = {
  permission: 'default',
  requestPermission: jest.fn().mockResolvedValue('granted'),
  new: jest.fn(),
};


// Mock ResizeObserver
window.ResizeObserver = class ResizeObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Fix for antd components using portals
// This is a workaround for antd components that use portals
// It ensures that the popups are rendered within the test container
// so that they can be found by the testing library.
require('antd').ConfigProvider.config({
  getPopupContainer: (node) => node || document.body,
});
