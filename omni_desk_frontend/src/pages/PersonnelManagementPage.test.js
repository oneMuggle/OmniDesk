import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import PersonnelManagementPage from './PersonnelManagementPage';
import {
  getPersonnel,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
  createPosition,
} from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockPersonnel = {
  results: [
    { id: 1, name: 'John Doe', position: 1, position_name: 'Developer', phone_numbers: [{ number: '12345' }] },
    { id: 2, name: 'Jane Smith', position: 2, position_name: 'Manager', phone_numbers: [{ number: '67890' }] },
  ],
  count: 2,
};

const mockPositions = {
  results: [
    { id: 1, name: 'Developer' },
    { id: 2, name: 'Manager' },
  ],
};

describe('PersonnelManagementPage', () => {
  beforeEach(() => {
    getPersonnel.mockResolvedValue(mockPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    createPersonnel.mockResolvedValue({});
    updatePersonnel.mockResolvedValue({});
    deletePersonnel.mockResolvedValue({});
    createPosition.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the component and fetches data', async () => {
    render(<MemoryRouter><PersonnelManagementPage /></MemoryRouter>);
    await waitFor(() => expect(getPersonnel).toHaveBeenCalled());
    await waitFor(() => expect(getPositions).toHaveBeenCalled());
    expect(await screen.findByText('John Doe')).toBeInTheDocument();
    expect(await screen.findByText('Jane Smith')).toBeInTheDocument();
  });

  describe('Personnel Management', () => {
    test('adds a new person', async () => {
      render(<MemoryRouter><PersonnelManagementPage /></MemoryRouter>);
      await screen.findByText('John Doe');

      fireEvent.click(screen.getByTestId('add-personnel-button'));
      await screen.findByTestId('personnel-modal');

      fireEvent.change(screen.getByTestId('personnel-modal-name-input'), { target: { value: 'Peter Pan' } });
      
      // Use userEvent for more reliable interaction with Ant Design's Select
      // Use userEvent for more reliable interaction with Ant Design's Select
      // Use userEvent for more reliable interaction with Ant Design's Select
      // Use userEvent for more reliable interaction with Ant Design's Select
      await userEvent.click(screen.getByTestId('personnel-modal-position-select'));
      await userEvent.click(await screen.findByText('Developer'));
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('personnel-modal-ok-button'));

      await waitFor(() => {
        expect(createPersonnel).toHaveBeenCalledWith(expect.objectContaining({ name: 'Peter Pan', position: 1 }));
      });
    });

    test('edits an existing person', async () => {
      render(<MemoryRouter><PersonnelManagementPage /></MemoryRouter>);
      await screen.findByText('John Doe');

      fireEvent.click(screen.getByLabelText('edit-personnel-1'));
      await screen.findByTestId('personnel-modal');

      fireEvent.change(screen.getByTestId('personnel-modal-name-input'), { target: { value: 'John Doe Updated' } });
      fireEvent.click(screen.getByTestId('personnel-modal-ok-button'));

      await waitFor(() => {
        expect(updatePersonnel).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'John Doe Updated' }));
      });
    });

    test('deletes an existing person', async () => {
      render(<MemoryRouter><PersonnelManagementPage /></MemoryRouter>);
      await screen.findByText('John Doe');

      fireEvent.click(screen.getByLabelText('delete-personnel-1'));

      await waitFor(() => {
        expect(screen.getByTestId('delete-personnel-confirm-modal')).toBeVisible();
      });
      fireEvent.click(screen.getByTestId('delete-personnel-confirm-modal-ok-button'));

      await waitFor(() => {
        expect(deletePersonnel).toHaveBeenCalledWith(1);
      });
    });

    test('searches and filters personnel', async () => {
      getPositions.mockResolvedValue(mockPositions); // Ensure positions are loaded
      render(<MemoryRouter><PersonnelManagementPage /></MemoryRouter>);
      await screen.findByText('John Doe');
    
      const searchInput = screen.getByPlaceholderText('按姓名搜索');
      fireEvent.change(searchInput, { target: { value: 'John' } });
      fireEvent.keyDown(searchInput, { key: 'Enter', code: 'Enter' });
    
      // The search triggers two calls: one from onSearch, one from useEffect.
      // We wait for the call that includes the search term.
      await waitFor(() => {
        expect(getPersonnel).toHaveBeenCalledWith(expect.objectContaining({ search: 'John' }));
      });
    
      const positionFilter = screen.getByTestId('personnel-position-filter');
      await userEvent.click(positionFilter);
      await userEvent.click(await screen.findByText('Developer'));
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByText('Developer', { selector: '.ant-select-selection-item' })).toBeInTheDocument();
      });

      // The filter change also triggers more calls. We wait for the final correct call.
      await waitFor(() => {
        expect(getPersonnel).toHaveBeenLastCalledWith(expect.objectContaining({ position: 1, search: 'John' }));
      });
    });
  });

});