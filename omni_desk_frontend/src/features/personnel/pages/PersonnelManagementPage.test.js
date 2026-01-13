import React from 'react';
import { render, screen, waitFor, within, waitForElementToBeRemoved } from '@testing-library/react';
import { ConfigProvider } from 'antd';
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
  getAllPositions,
  createPosition,
  updatePosition,
  deletePosition,
} from '../api/personnelApi';
import { message } from 'antd';

jest.mock('antd', () => {
  const antd = jest.requireActual('antd');
  const message = {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
    info: jest.fn(),
  };
  // Mock Modal.confirm to automatically call onOk
  const Modal = {
    ...antd.Modal,
    confirm: jest.fn(({ onOk }) => {
      if (onOk) {
        // We wrap onOk in a promise resolve to simulate the async nature
        // of user interaction and subsequent API calls.
        return Promise.resolve(onOk());
      }
    }),
  };
  return { ...antd, message, Modal };
});


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
  let container;
  let mutablePersonnel;
  let mutablePositions;

  const renderWithProvider = (ui) => {
    return render(
      <MemoryRouter>
        <ConfigProvider getPopupContainer={() => container}>
          {ui}
        </ConfigProvider>
      </MemoryRouter>,
      { container }
    );
  };

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);

    mutablePersonnel = JSON.parse(JSON.stringify(mockPersonnel.results));
    mutablePositions = JSON.parse(JSON.stringify(mockPositions.results));

    getPersonnel.mockImplementation(({ page = 1, page_size = 10 } = {}) => {
      const start = (page - 1) * page_size;
      const end = start + page_size;
      const paginatedData = mutablePersonnel.slice(start, end);
      return Promise.resolve({ data: paginatedData, pagination: { total: mutablePersonnel.length } });
    });

    getPositions.mockImplementation(() => Promise.resolve({ data: mutablePositions }));
    getAllPositions.mockResolvedValue(mutablePositions);

    createPersonnel.mockImplementation(newData => {
      const position = mutablePositions.find(p => p.id === newData.position);
      const newPerson = {
        ...newData,
        id: Date.now(),
        position_name: position ? position.name : '',
        phone_numbers: newData.phone_numbers || [],
      };
      mutablePersonnel.push(newPerson);
      return Promise.resolve(newPerson);
    });

    deletePersonnel.mockImplementation(id => {
      const index = mutablePersonnel.findIndex(p => p.id === id);
      if (index > -1) {
        mutablePersonnel.splice(index, 1);
        return Promise.resolve({});
      }
      return Promise.reject(new Error('Personnel not found'));
    });

    createPosition.mockImplementation(newData => {
      const newPosition = { ...newData, id: Date.now() };
      mutablePositions.push(newPosition);
      return Promise.resolve(newPosition);
    });

    updatePosition.mockImplementation((id, updatedData) => {
      const index = mutablePositions.findIndex(p => p.id === id);
      if (index > -1) {
        mutablePositions[index] = { ...mutablePositions[index], ...updatedData };
        return Promise.resolve(mutablePositions[index]);
      }
      return Promise.reject(new Error('Position not found'));
    });

    deletePosition.mockImplementation(id => {
      const index = mutablePositions.findIndex(p => p.id === id);
      if (index > -1) {
        mutablePositions.splice(index, 1);
        return Promise.resolve({});
      }
      return Promise.reject(new Error('Position not found'));
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
    if (container) {
      document.body.removeChild(container);
      container = null;
    }
  });

  test('renders the component and fetches data', async () => {
    renderWithProvider(<PersonnelManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getByText(/共 2 条/)).toBeInTheDocument();
    });
  });

  test('shows error message when fetching personnel fails', async () => {
    getPersonnel.mockRejectedValue(new Error('Failed to fetch'));
    renderWithProvider(<PersonnelManagementPage />);
    await waitFor(() => {
      expect(message.error).toHaveBeenCalledWith('获取人员数据失败');
    });
  });

  describe('Personnel Management', () => {
    test('adds a new person with dynamic phone numbers', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe');

      await userEvent.click(screen.getByRole('button', { name: /新增人员/i }));
      const dialog = await screen.findByRole('dialog');

      await userEvent.type(within(dialog).getByLabelText('姓名'), 'Peter Pan');
      await userEvent.click(within(dialog).getByLabelText('职位'));
      await userEvent.click(await screen.findByText('Developer'));

      // Add a phone number
      await userEvent.click(within(dialog).getByRole('button', { name: /添加电话号码/i }));
      await userEvent.type(within(dialog).getAllByPlaceholderText('电话号码')[0], '12345678901');

      // Add another phone number and then remove it
      await userEvent.click(within(dialog).getByRole('button', { name: /添加电话号码/i }));
      await userEvent.type(within(dialog).getAllByPlaceholderText('电话号码')[1], '111');
      await userEvent.click(within(dialog).getAllByRole('img', { name: /minus-circle/i })[1]);


      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPersonnel).toHaveBeenCalledWith(expect.objectContaining({
          name: 'Peter Pan',
          position: 1,
          phone_numbers: [{ number: '12345678901' }],
        }));
        expect(message.success).toHaveBeenCalledWith('创建成功');
      });
    });

    test('deletes an existing person and handles API failure', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe');

      // Test successful deletion
      await userEvent.click(screen.getAllByRole('button', { name: /删除/i })[0]);
      await waitFor(() => {
        expect(deletePersonnel).toHaveBeenCalledWith(1);
        expect(message.success).toHaveBeenCalledWith('删除成功');
        expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      });

      // Test failed deletion
      deletePersonnel.mockRejectedValueOnce(new Error('Deletion failed'));
      await userEvent.click(screen.getAllByRole('button', { name: /删除/i })[0]); // Delete Jane Smith
      await waitFor(() => {
        expect(deletePersonnel).toHaveBeenCalledWith(2);
        expect(message.error).toHaveBeenCalledWith('删除失败');
      });
    });

    test('handles pagination change', async () => {
      // Add more mock data to test pagination
      for (let i = 3; i <= 15; i++) {
        mutablePersonnel.push({ id: i, name: `Person ${i}`, position: 1, position_name: 'Developer', phone_numbers: [] });
      }
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe');

      // Navigate to the next page
      await userEvent.click(screen.getByTitle('Next Page'));

      await waitFor(() => {
        // Wait for the second page's content to appear
        expect(screen.getByText('Person 11')).toBeInTheDocument();
      });
      // Assert API calls after waiting
      expect(getPersonnel).toHaveBeenCalledTimes(2);
      expect(getPersonnel).toHaveBeenCalledWith({ page: 2, page_size: 10 });
    });
  });

  describe('Position Management Tab', () => {
    test('renders position data and allows creating a new position', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const positionTab = await screen.findByRole('tab', { name: /职位管理/i });
      await userEvent.click(positionTab);

      await screen.findByText('职位管理'); // Header for the tab content
      expect(screen.getByText('Developer')).toBeInTheDocument();

      await userEvent.click(screen.getByRole('button', { name: /新增职位/i }));
      const dialog = await screen.findByRole('dialog', { name: /新增职位/i });

      await userEvent.type(within(dialog).getByLabelText('职位名称'), 'QA Tester');
      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPosition).toHaveBeenCalledWith({ name: 'QA Tester' });
        expect(message.success).toHaveBeenCalledWith('职位创建成功');
        expect(screen.getByText('QA Tester')).toBeInTheDocument();
      });
    });

    test('allows editing an existing position', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const positionTab = await screen.findByRole('tab', { name: /职位管理/i });
      await userEvent.click(positionTab);

      await screen.findByText('Developer');
      await userEvent.click(screen.getAllByRole('button', { name: /编辑/i })[0]);

      const dialog = await screen.findByRole('dialog', { name: /编辑职位/i });
      const input = within(dialog).getByLabelText('职位名称');
      await userEvent.clear(input);
      await userEvent.type(input, 'Senior Developer');
      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(updatePosition).toHaveBeenCalledWith(1, { name: 'Senior Developer' });
        expect(message.success).toHaveBeenCalledWith('职位更新成功');
        expect(screen.getByText('Senior Developer')).toBeInTheDocument();
      });
    });

    test('allows deleting a position and handles API failure', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const positionTab = await screen.findByRole('tab', { name: /职位管理/i });
      await userEvent.click(positionTab);

      await screen.findByText('Developer');

      // Successful deletion
      await userEvent.click(screen.getAllByRole('button', { name: /删除/i })[1]); // Delete 'Manager'
      await waitFor(() => {
        expect(deletePosition).toHaveBeenCalledWith(2);
        expect(message.success).toHaveBeenCalledWith('职位删除成功');
        expect(screen.queryByText('Manager')).not.toBeInTheDocument();
      });

      // Failed deletion
      deletePosition.mockRejectedValueOnce(new Error('Deletion failed'));
      await userEvent.click(screen.getAllByRole('button', { name: /删除/i })[0]); // Delete 'Developer'
      await waitFor(() => {
        expect(deletePosition).toHaveBeenCalledWith(1);
        expect(message.error).toHaveBeenCalledWith('职位删除失败');
      });
    });
  });
});