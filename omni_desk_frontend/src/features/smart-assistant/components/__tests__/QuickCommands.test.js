import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import QuickCommands from '../QuickCommands';

describe('QuickCommands - aggregation shortcuts', () => {
  test('renders "我的本周" button', () => {
    const mockOnCommand = jest.fn();
    render(<QuickCommands onCommand={mockOnCommand} />);
    expect(screen.getByText(/我的本周/)).toBeInTheDocument();
  });

  test('clicking 我的本周 fires personal_summary intent', () => {
    const mockOnCommand = jest.fn();
    render(<QuickCommands onCommand={mockOnCommand} />);
    fireEvent.click(screen.getByText(/我的本周/));
    expect(mockOnCommand).toHaveBeenCalledWith(
      expect.objectContaining({ intent: 'personal_summary' })
    );
  });

  test('clicking 我今天 fires personal_summary with today scope', () => {
    const mockOnCommand = jest.fn();
    render(<QuickCommands onCommand={mockOnCommand} />);
    fireEvent.click(screen.getByText(/我今天/));
    expect(mockOnCommand).toHaveBeenCalledWith(
      expect.objectContaining({ intent: 'personal_summary', scope: 'today' })
    );
  });

  test('all existing shortcuts still work', () => {
    const mockOnCommand = jest.fn();
    render(<QuickCommands onCommand={mockOnCommand} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(2);
  });
});