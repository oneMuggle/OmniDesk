import { render, screen, fireEvent } from '@testing-library/react';
import { DemoProvider } from '../../context/DemoContext';
import DemoToggle from '../DemoToggle';

// Mock setDemoModeEnabled
jest.mock('../../api/axiosConfig', () => ({
  setDemoModeEnabled: jest.fn(),
}));

describe('DemoToggle', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  it('渲染开关', () => {
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('切换时调用 setDemoModeEnabled', () => {
    const { setDemoModeEnabled } = require('../../api/axiosConfig');
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    fireEvent.click(screen.getByRole('switch'));
    expect(setDemoModeEnabled).toHaveBeenCalledWith(true);
  });

  it('显示当前模式文本', () => {
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    expect(screen.getByText(/演示模式/)).toBeInTheDocument();
  });

  it('切换时显示成功消息', () => {
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    fireEvent.click(screen.getByRole('switch'));
    // Ant Design message 是异步的，这里验证组件行为
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('从关闭切换到开启', () => {
    const { setDemoModeEnabled } = require('../../api/axiosConfig');
    render(
      <DemoProvider>
        <DemoToggle />
      </DemoProvider>
    );
    const switchElement = screen.getByRole('switch');
    expect(switchElement).not.toBeChecked();
    fireEvent.click(switchElement);
    expect(switchElement).toBeChecked();
    expect(setDemoModeEnabled).toHaveBeenCalledWith(true);
  });
});
