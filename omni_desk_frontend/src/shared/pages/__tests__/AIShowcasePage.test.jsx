import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import AIShowcasePage from '../AIShowcasePage';

// Mock react-router-dom's useNavigate
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

describe('AIShowcasePage', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('渲染页面标题', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText(/AI 能力展示/)).toBeInTheDocument();
  });

  it('渲染 Dify 卡片', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const elements = screen.getAllByText(/Dify/);
    expect(elements.length).toBeGreaterThan(0);
  });

  it('渲染 RAGFlow 卡片', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const elements = screen.getAllByText(/RAGFlow/);
    expect(elements.length).toBeGreaterThan(0);
  });

  it('包含"立即体验"按钮', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const buttons = screen.getAllByText(/立即体验/);
    expect(buttons.length).toBeGreaterThanOrEqual(2);
  });

  it('渲染 Dify 特性列表', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText('智能客服助手')).toBeInTheDocument();
    expect(screen.getByText('合同审查工具')).toBeInTheDocument();
    expect(screen.getByText('员工手册问答')).toBeInTheDocument();
  });

  it('渲染 RAGFlow 特性列表', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText('企业知识库问答')).toBeInTheDocument();
    expect(screen.getByText('产品文档检索')).toBeInTheDocument();
    expect(screen.getByText('多轮对话支持')).toBeInTheDocument();
  });

  it('Dify 按钮点击跳转到 /dify-apps', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const buttons = screen.getAllByText(/立即体验/);
    fireEvent.click(buttons[0]); // First button is Dify
    expect(mockNavigate).toHaveBeenCalledWith('/dify-apps');
  });

  it('RAGFlow 按钮点击跳转到 /ragflow-chat', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    const buttons = screen.getAllByText(/立即体验/);
    fireEvent.click(buttons[1]); // Second button is RAGFlow
    expect(mockNavigate).toHaveBeenCalledWith('/ragflow-chat');
  });

  it('显示演示模式提示', () => {
    render(
      <MemoryRouter>
        <AIShowcasePage />
      </MemoryRouter>
    );
    expect(screen.getByText(/演示模式/)).toBeInTheDocument();
  });
});
