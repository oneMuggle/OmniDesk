import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import QuickCommands from '../QuickCommands';

describe('QuickCommands - aggregation shortcuts', () => {
  test('renders "我的本周" button', () => {
    const mockOnSend = jest.fn();
    render(<QuickCommands onSend={mockOnSend} />);
    expect(screen.getByText(/我的本周/)).toBeInTheDocument();
  });

  test('clicking 我的本周 translates personal_summary+week into a natural-language query', () => {
    // Task 17 fix C4: 前端把 {intent, scope} 翻译为自然语言 query 走 onSend
    const mockOnSend = jest.fn();
    render(<QuickCommands onSend={mockOnSend} />);
    fireEvent.click(screen.getByText(/我的本周/));
    expect(mockOnSend).toHaveBeenCalledWith('这周我有哪些事');
  });

  test('clicking 我今天 translates personal_summary+today into a natural-language query', () => {
    const mockOnSend = jest.fn();
    render(<QuickCommands onSend={mockOnSend} />);
    fireEvent.click(screen.getByText(/我今天/));
    expect(mockOnSend).toHaveBeenCalledWith('今天有什么安排');
  });

  test('all existing shortcuts still work', () => {
    const mockOnSend = jest.fn();
    render(<QuickCommands onSend={mockOnSend} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(2);
  });

  test('falls back to onCommand when onSend is not provided', () => {
    // 兼容旧调用方:仅有 onCommand 时按原方式透传
    const mockOnCommand = jest.fn();
    render(<QuickCommands onCommand={mockOnCommand} />);
    fireEvent.click(screen.getByText(/我的本周/));
    expect(mockOnCommand).toHaveBeenCalledWith(
      expect.objectContaining({ intent: 'personal_summary' })
    );
  });
});
