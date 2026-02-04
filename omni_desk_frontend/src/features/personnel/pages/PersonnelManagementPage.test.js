import React from 'react';
import { render, screen, waitFor, within, waitForElementToBeRemoved } from '@testing-library/react';
import { ConfigProvider, Modal } from 'antd';
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

  // The original Modal is returned, and we will use jest.spyOn to mock `Modal.confirm`.
  return { ...antd, message };
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
    jest.spyOn(Modal, 'confirm').mockImplementation(async (config) => {
      if (config.onOk) {
        try {
          // onOk is async, so we should await it.
          await config.onOk();
        } catch (e) {
          // In failure tests, onOk might reject, which is expected.
          // We can ignore the rejection here as the test will assert the outcome (e.g., error message).
        }
      }
      // Modal.confirm returns a promise that resolves when the modal is closed.
      // We can return a resolved promise to simulate this.
      return Promise.resolve();
    });

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

    getPositions.mockImplementation(() => Promise.resolve({ data: { results: mutablePositions } }));
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
        return Promise.resolve({ data: { results: mutablePositions } });
      }
      return Promise.reject(new Error('Position not found'));
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
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
    test('adds a new person', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe');

      await userEvent.click(screen.getByRole('button', { name: /新增人员/i }));
      const dialog = await screen.findByRole('dialog');

      await userEvent.type(within(dialog).getByLabelText('姓名'), 'Peter Pan');
      
      // Select a position
      await userEvent.click(within(dialog).getByLabelText('职位'));
      await screen.findByText('Developer'); // Wait for options to appear
      await userEvent.click(screen.getByText('Developer'));

      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPersonnel).toHaveBeenCalledWith({ name: 'Peter Pan', position: 1 });
        expect(message.success).toHaveBeenCalledWith('创建成功');
      });
      // Verify the new person is in the table
      await screen.findByText('Peter Pan');
    });

    test('deletes an existing person and handles API failure', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe');

      // Test successful deletion
      const johnDoeRow = await screen.findByRole('row', { name: /John Doe/i });
      const deleteButton = within(johnDoeRow).getByRole('button', { name: /删除/i });
      await userEvent.click(deleteButton);
      await waitFor(() => {
        expect(deletePersonnel).toHaveBeenCalledWith(1);
        expect(message.success).toHaveBeenCalledWith('删除成功');
        expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      });

      // Test failed deletion
      deletePersonnel.mockRejectedValueOnce(new Error('Deletion failed'));
      const janeSmithRow = await screen.findByRole('row', { name: /Jane Smith/i });
      const deleteButtonJane = within(janeSmithRow).getByRole('button', { name: /删除/i });
      await userEvent.click(deleteButtonJane);
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

      const positionTabPanel = await screen.findByRole('tabpanel'); // Find the active tab panel

      // Scope all queries within the position management tab panel
      await within(positionTabPanel).findByRole('heading', { name: '职位管理' });
      expect(within(positionTabPanel).getByText('Developer')).toBeInTheDocument();

      await userEvent.click(within(positionTabPanel).getByRole('button', { name: /新增职位/i }));
      const dialog = await screen.findByRole('dialog', { name: /新增职位/i });

      await userEvent.type(within(dialog).getByLabelText('职位名称'), 'QA Tester');
      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(createPosition).toHaveBeenCalledWith({ name: 'QA Tester' });
        expect(message.success).toHaveBeenCalledWith('职位创建成功');
        expect(within(positionTabPanel).getByText('QA Tester')).toBeInTheDocument();
      });
    });

    test('allows editing an existing position', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const positionTab = await screen.findByRole('tab', { name: /职位管理/i });
      await userEvent.click(positionTab);

      const positionTabPanel = await screen.findByRole('tabpanel');

      await within(positionTabPanel).findByText('Developer');
      // Use within to scope the search for the edit button
      const developerRow = await within(positionTabPanel).findByRole('row', { name: /Developer/i });
      await userEvent.click(within(developerRow).getByRole('button', { name: /编辑/i }));

      const dialog = await screen.findByRole('dialog', { name: /编辑职位/i });
      const input = within(dialog).getByLabelText('职位名称');
      await userEvent.clear(input);
      await userEvent.type(input, 'Senior Developer');
      await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

      await waitFor(() => {
        expect(updatePosition).toHaveBeenCalledWith(1, { name: 'Senior Developer' });
        expect(message.success).toHaveBeenCalledWith('职位更新成功');
        expect(within(positionTabPanel).getByText('Senior Developer')).toBeInTheDocument();
      });
    });

    test('allows deleting a position and handles API failure', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const positionTab = await screen.findByRole('tab', { name: /职位管理/i });
      await userEvent.click(positionTab);

      const positionTabPanel = await screen.findByRole('tabpanel');

      await within(positionTabPanel).findByText('Developer');

      // Successful deletion
      // The `findByRole('row', ...)` query can be unreliable. A more robust method is to
      // find all rows and then identify the specific one containing the "Manager" text.
      const rows = await within(positionTabPanel).findAllByRole('row');
      const managerRow = rows.find(row => within(row).queryByText('Manager'));
      const deleteButtonManager = within(managerRow).getByRole('button', { name: /删除/i });
      await userEvent.click(deleteButtonManager);
      await waitFor(() => {
        expect(deletePosition).toHaveBeenCalledWith(2);
        expect(message.success).toHaveBeenCalledWith('职位删除成功');
        expect(within(positionTabPanel).queryByText('Manager')).not.toBeInTheDocument();
      });

      // Failed deletion
      deletePosition.mockRejectedValueOnce(new Error('Deletion failed'));
      const developerRow = await within(positionTabPanel).findByRole('row', { name: /Developer/i });
      const deleteButtonDeveloper = within(developerRow).getByRole('button', { name: /删除/i });
      await userEvent.click(deleteButtonDeveloper);
      await waitFor(() => {
        expect(deletePosition).toHaveBeenCalledWith(1);
        expect(message.error).toHaveBeenCalledWith('职位删除失败');
        expect(within(positionTabPanel).getByText('Developer')).toBeInTheDocument();
      });
    });
  });
});