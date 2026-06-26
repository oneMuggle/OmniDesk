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
    jest.resetAllMocks();
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
