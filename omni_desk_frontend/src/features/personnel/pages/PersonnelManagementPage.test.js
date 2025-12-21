
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
} from '../api/personnelApi';

jest.mock('antd', () => {
  const antd = jest.requireActual('antd');
  return {
    ...antd,
    message: {
      success: jest.fn(),
      error: jest.fn(),
      warning: jest.fn(),
      info: jest.fn(),
    },
  };
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

  const renderWithProvider = (ui) => {
    // By rendering into a container and telling antd to use that container for popups,
    // we can reliably find elements within those popups.
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
    // eslint-disable-next-line testing-library/no-node-access
    container = document.createElement('div');
    // eslint-disable-next-line testing-library/no-node-access
    document.body.appendChild(container);

    // Use a mutable list to simulate backend state changes across API calls in a single test
    const mutablePersonnel = JSON.parse(JSON.stringify(mockPersonnel.results));

    getPersonnel.mockImplementation(params => {
      const { search, position } = params || {};
      let results = [...mutablePersonnel];
      if (search) {
        results = results.filter(p =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          (p.phone_numbers && p.phone_numbers.some(ph => ph.number.includes(search)))
        );
      }
      if (position) {
        // Ensure position is treated as a number for comparison
        results = results.filter(p => p.position === parseInt(String(position), 10));
      }
      return Promise.resolve({ data: results, pagination: { total: results.length } });
    });

    getPositions.mockResolvedValue({ data: mockPositions.results });
    getAllPositions.mockResolvedValue(mockPositions.results);

    createPersonnel.mockImplementation(newData => {
      const position = mockPositions.results.find(p => p.id === newData.position);
      const newPerson = {
        ...newData,
        id: Date.now(), // Simple unique ID for testing
        position_name: position ? position.name : '',
        phone_numbers: newData.phone_numbers || [],
      };
      mutablePersonnel.push(newPerson);
      return Promise.resolve(newPerson);
    });

    updatePersonnel.mockImplementation((id, updatedData) => {
      const index = mutablePersonnel.findIndex(p => p.id === id);
      if (index > -1) {
        mutablePersonnel[index] = { ...mutablePersonnel[index], ...updatedData };
        return Promise.resolve(mutablePersonnel[index]);
      }
      return Promise.reject(new Error('Personnel not found'));
    });

    deletePersonnel.mockImplementation(id => {
      const index = mutablePersonnel.findIndex(p => p.id === id);
      if (index > -1) {
        mutablePersonnel.splice(index, 1);
        return Promise.resolve({});
      }
      return Promise.reject(new Error('Personnel not found'));
    });

    createPosition.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
    if (container) {
      // eslint-disable-next-line testing-library/no-node-access
      document.body.removeChild(container);
      container = null;
    }
  });

  test('renders the component and fetches data', async () => {
    renderWithProvider(<PersonnelManagementPage />);
    // findBy* queries wait for the element to appear, handling the async useEffect fetch.
    expect(await screen.findByText('John Doe')).toBeInTheDocument();
    expect(await screen.findByText('Jane Smith')).toBeInTheDocument();
  });

  describe('Personnel Management', () => {
    test('adds a new person', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe'); // Wait for initial data

      await userEvent.click(screen.getByRole('button', { name: /新增人员/i }));
      await screen.findByRole('dialog');

      await userEvent.type(screen.getByLabelText('姓名'), 'Peter Pan');
      
      const positionSelect = screen.getByLabelText('职位');
      await userEvent.click(positionSelect);
      await screen.findByRole('listbox');
      // The first option is 'Developer' with id 1
      await userEvent.keyboard('{enter}');

      await userEvent.click(screen.getByRole('button', { name: 'OK' }));

      // Wait for the new person to appear in the table. This confirms the re-fetch and re-render.
      expect(await screen.findByText('Peter Pan')).toBeInTheDocument();
      // Verify the API call was made correctly.
      expect(createPersonnel).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Peter Pan',
        position: 1,
      }));
    });

    test('edits an existing person', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      await screen.findByText('John Doe'); // Wait for initial data

      await userEvent.click(screen.getAllByRole('button', { name: /编辑/i })[0]);
      await screen.findByRole('dialog');

      await userEvent.clear(screen.getByLabelText('姓名'));
      await userEvent.type(screen.getByLabelText('姓名'), 'John Doe Updated');
      await userEvent.click(screen.getByRole('button', { name: 'OK' }));

      // Wait for the updated name to appear, confirming re-fetch and re-render.
      expect(await screen.findByText('John Doe Updated')).toBeInTheDocument();
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();

      // Verify the API call.
      expect(updatePersonnel).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'John Doe Updated' }));
    });

    test('deletes an existing person', async () => {
      renderWithProvider(<PersonnelManagementPage />);
      const johnDoeElement = await screen.findByText('John Doe'); // Wait for initial data

      await userEvent.click(screen.getAllByRole('button', { name: /删除/i })[0]);

      const dialog = await screen.findByRole('dialog');
      const confirmButton = await within(dialog).findByRole('button', { name: /确\s*认/ });
      await userEvent.click(confirmButton);

      // Wait for the element to be removed from the DOM, confirming re-fetch and re-render.
      await waitForElementToBeRemoved(johnDoeElement);

      // Verify the API call and the DOM state.
      expect(deletePersonnel).toHaveBeenCalledWith(1);
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
    });

  });
});