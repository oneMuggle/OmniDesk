import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ScheduleSettingsPage from './ScheduleSettingsPage';

// Mock the child component
jest.mock('./SequenceManager', () => () => <div>SequenceManager Mock</div>);

describe('ScheduleSettingsPage', () => {
  test('renders the page with title and the SequenceManager component', () => {
    render(<ScheduleSettingsPage />);

    expect(screen.getByRole('heading', { name: /排班设置/i })).toBeInTheDocument();
    expect(screen.getByText('在这里管理您的排班顺序。')).toBeInTheDocument();
    expect(screen.getByText('SequenceManager Mock')).toBeInTheDocument();
  });
});