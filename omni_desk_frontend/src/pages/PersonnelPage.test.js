import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PersonnelPage from './PersonnelPage';
import {
  getPersonnel,
  createPersonnel,
  updatePersonnel,
  deletePersonnel,
  getPositions,
  createPosition,
  updatePosition,
  deletePosition,
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

describe('PersonnelPage', () => {
  beforeEach(() => {
    getPersonnel.mockResolvedValue(mockPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    createPersonnel.mockResolvedValue({});
    updatePersonnel.mockResolvedValue({});
    deletePersonnel.mockResolvedValue({});
    createPosition.mockResolvedValue({});
    updatePosition.mockResolvedValue({});
    deletePosition.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the component and fetches data', async () => {
    render(<PersonnelPage />);

    expect(screen.getByRole('heading', { name: /人员管理系统/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(getPersonnel).toHaveBeenCalled();
    });
    expect(getPositions).toHaveBeenCalled();

    await screen.findByText('John Doe');
    await screen.findByText('Jane Smith');
  });

  describe('Personnel Management', () => {
    test('adds a new person', async () => {
      render(<PersonnelPage />);

      fireEvent.click(screen.getByRole('button', { name: /新增人员/i }));
      await screen.findByRole('dialog', { name: /新增人员/i });

      fireEvent.change(screen.getByLabelText('姓名'), { target: { value: 'Peter Pan' } });
      fireEvent.mouseDown(screen.getByLabelText('职位'));
      const developerOptions = await screen.findAllByText('Developer');
      fireEvent.click(developerOptions[0]);

      fireEvent.click(screen.getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPersonnel).toHaveBeenCalledWith(expect.objectContaining({ name: 'Peter Pan' }));
      });
    });

    test('edits an existing person', async () => {
      render(<PersonnelPage />);

      await screen.findByText('John Doe');
      const editButtons = await screen.findAllByRole('button', { name: /编辑/i });
      fireEvent.click(editButtons[0]);

      await screen.findByRole('dialog', { name: /编辑人员/i });
      expect(screen.getByLabelText('姓名')).toHaveValue('John Doe');

      fireEvent.change(screen.getByLabelText('姓名'), { target: { value: 'John Doe Updated' } });
      fireEvent.click(screen.getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(updatePersonnel).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'John Doe Updated' }));
      });
    });

    test('deletes an existing person', async () => {
      render(<PersonnelPage />);

      await screen.findByText('John Doe');
      const deleteButtons = await screen.findAllByRole('button', { name: /删除/i });
      fireEvent.click(deleteButtons[0]);

      await screen.findByText('确定要删除该人员信息吗？');
      fireEvent.click(screen.getByRole('button', { name: /确认/i }));

      await waitFor(() => {
        expect(deletePersonnel).toHaveBeenCalledWith(1);
      });
    });

    test('searches and filters personnel', async () => {
        render(<PersonnelPage />);
      
        const searchInput = screen.getByPlaceholderText('按姓名搜索');
        fireEvent.change(searchInput, { target: { value: 'John' } });
        fireEvent.keyDown(searchInput, { key: 'Enter', code: 'Enter' });
      
        await waitFor(() => {
          expect(getPersonnel).toHaveBeenCalledWith(expect.objectContaining({ search: 'John' }));
        });
      
        // Cannot directly test Select change in JSDOM easily, but we can check if the API is called with the filter
        // This part of the test is more of an integration test
    });
  });

  describe('Position Management', () => {
    test('switches to position management tab and adds a new position', async () => {
      render(<PersonnelPage />);

      fireEvent.click(screen.getByRole('tab', { name: /职位管理/i }));
      await screen.findByRole('heading', { name: /职位管理/i });

      fireEvent.click(screen.getByRole('button', { name: /新增职位/i }));
      await screen.findByRole('dialog', { name: /新增职位/i });

      fireEvent.change(screen.getByLabelText('职位名称'), { target: { value: 'Tester' } });
      fireEvent.click(screen.getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPosition).toHaveBeenCalledWith({ name: 'Tester' });
      });
    });
  });
});