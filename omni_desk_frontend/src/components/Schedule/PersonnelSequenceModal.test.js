import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import apiClient from '../../api/apiClient';
import PersonnelSequenceModal from './PersonnelSequenceModal';

jest.mock('../../api/apiClient');

const mockPositions = [
  { id: 1, name: 'Manager' },
  { id: 2, name: 'Developer' },
];

const mockPersonnel = {
  results: [
    { id: 1, name: 'Alice', position: 'Developer' },
    { id: 2, name: 'Bob', position: 'Manager' },
    { id: 3, name: 'Charlie', position: 'Designer' },
  ],
};

describe('PersonnelSequenceModal', () => {
  beforeEach(() => {
    apiClient.get.mockImplementation((url) => {
      if (url.includes('/personnel/positions')) {
        return Promise.resolve({ data: mockPositions });
      }
      if (url.includes('/personnel/personnel')) {
        return Promise.resolve({ data: mockPersonnel });
      }
      return Promise.reject(new Error('not found'));
    });
    apiClient.post.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the modal and fetches initial data', async () => {
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    expect(screen.getByText('新建人员顺序')).toBeInTheDocument();
    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(await screen.findByText('Bob')).toBeInTheDocument();
  });

  test('allows adding and removing personnel for workday and holiday', async () => {
    const user = userEvent;
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    // Wait for personnel to load
    await screen.findByText('Alice');

    // Define containers
    // The query `getByRole('list')` is ambiguous as Ant Design's List component
    // renders multiple `<ul>` elements with the list role (for item actions).
    // We select the first element found, which corresponds to the main source list.
    const sourceListContainer = screen.getAllByRole('list')[0];
    
    // Add Alice to Workday
    const addButtons = screen.getAllByRole('button', { name: '添加' });
    await user.click(addButtons[0]);
    
    // After adding, there should be two "Alice" texts on the screen:
    // one in the source list and one in the selected list.
    await waitFor(() => {
      expect(screen.getAllByText('Alice').length).toBe(2);
    });

    // Switch to Holiday tab
    await user.click(screen.getByText('节假日人员'));

    // Add Bob to Holiday
    const addButtonsAgain = screen.getAllByRole('button', { name: '添加' });
    await user.click(addButtonsAgain[1]);
    
    // After adding Bob to the holiday list, there should be two "Bob" texts.
    await waitFor(() => {
      expect(screen.getAllByText('Bob').length).toBe(2);
    });

    // Remove Bob from Holiday
    // There are multiple remove buttons, we need to find the one for Bob in the holiday list.
    // Since we just added Bob, he will be the last one.
    const removeButtons = screen.getAllByRole('button', { name: 'X' });
    await user.click(removeButtons[removeButtons.length - 1]);
    
    // After removing, there should be only one "Bob" text left (in the source list).
    await waitFor(() => {
      expect(screen.getAllByText('Bob').length).toBe(1);
    });
  });

  test('allows searching and filtering personnel', async () => {
    const user = userEvent;
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    // Wait for initial data to load
    await screen.findByText('Alice');

    // Search for personnel
    await user.type(screen.getByPlaceholderText('按姓名拼音搜索'), 'Ali');
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/personnel/personnel/', { params: { search: 'Ali', position_id: null } });
    });

    // Filter by position
    // Click the combobox to open the dropdown
    const positionSelect = screen.getByRole('combobox');
    await user.click(positionSelect);
    // Pressing Enter should select the first option, which is 'Manager'
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/personnel/personnel/', { params: { search: 'Ali', position_id: 1 } });
    });
  });

  test('saves the personnel sequence', async () => {
    const user = userEvent;
    const onOk = jest.fn();
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={onOk} />);

    await screen.findByText('Alice');

    await user.type(screen.getByPlaceholderText('顺序名称'), 'Test Sequence');
    
    // Add Alice to workday
    const addButtons = screen.getAllByRole('button', { name: '添加' });
    await user.click(addButtons[0]);

    // Switch to holiday tab and add Bob
    await user.click(screen.getByText('节假日人员'));
    const addButtonsHoliday = screen.getAllByRole('button', { name: '添加' });
    await user.click(addButtonsHoliday[1]);

    // Click save
    await user.click(screen.getByRole('button', { name: /保\s*存/ }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/api/events/personnel-sequences/', {
        name: 'Test Sequence',
        personnel_ids: [1],
        holiday_personnel_ids: [2],
      });
    });
    
    await waitFor(() => {
      expect(onOk).toHaveBeenCalled();
    });
  });
});