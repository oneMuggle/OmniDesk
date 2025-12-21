import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ScheduleSettingsPage from '../../features/schedule/pages/ScheduleSettingsPage';

// Mock the child component
jest.mock('../../shared/components/SequenceManager', () => {
  const MockSequenceManager = () => <div>SequenceManager Mock</div>;
  MockSequenceManager.displayName = 'MockSequenceManager';
  return MockSequenceManager;
});

describe('ScheduleSettingsPage', () => {
  test('renders the page with title and the SequenceManager component', () => {
    render(<ScheduleSettingsPage />);

    expect(screen.getByRole('heading', { name: /排班设置/i })).toBeInTheDocument();
    expect(screen.getByText('在这里管理您的排班顺序。')).toBeInTheDocument();
    expect(screen.getByText('SequenceManager Mock')).toBeInTheDocument();
  });
});