import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import PositionManagementTab from './PositionManagementTab';
import { getPositions, createPosition, updatePosition, deletePosition } from '../../api/personnelApi';

jest.mock('../../api/personnelApi');

const mockPositions = {
  results: [
    { id: 1, name: 'Developer' },
    { id: 2, name: 'Manager' },
  ],
};

describe('PositionManagementTab', () => {
  beforeEach(() => {
    getPositions.mockResolvedValue(mockPositions);
    createPosition.mockResolvedValue({});
    updatePosition.mockResolvedValue({});
    deletePosition.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the component and fetches data', async () => {
    render(<PositionManagementTab />);
    await waitFor(() => expect(getPositions).toHaveBeenCalled());
    expect(await screen.findByText('Developer')).toBeInTheDocument();
    expect(await screen.findByText('Manager')).toBeInTheDocument();
  });

  test('adds a new position', async () => {
    render(<PositionManagementTab />);
    await screen.findByText('Developer');

    fireEvent.click(screen.getByTestId('add-position-button'));
    await screen.findByTestId('position-modal');

    fireEvent.change(screen.getByTestId('position-modal-name-input'), { target: { value: 'Tester' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(createPosition).toHaveBeenCalledWith({ name: 'Tester' });
    });
  });

  test('edits an existing position', async () => {
    render(<PositionManagementTab />);
    await screen.findByText('Developer');

    fireEvent.click(screen.getByTestId('edit-position-button-1'));
    await screen.findByTestId('position-modal');

    fireEvent.change(screen.getByTestId('position-modal-name-input'), { target: { value: 'Developer Updated' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(updatePosition).toHaveBeenCalledWith(1, { name: 'Developer Updated' });
    });
  });

  test('deletes an existing position', async () => {
    render(<PositionManagementTab />);
    await screen.findByText('Developer');

    fireEvent.click(screen.getByTestId('delete-position-button-1'));
    
    await screen.findByText('确定要删除该职位吗？');
    await userEvent.click(screen.getByRole('button', { name: '确认' }));

    await waitFor(() => {
      expect(deletePosition).toHaveBeenCalledWith(1);
    });
  });
});