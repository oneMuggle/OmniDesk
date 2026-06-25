import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIShowcasePage from '../AIShowcasePage';

describe('AIShowcasePage', () => {
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
});
