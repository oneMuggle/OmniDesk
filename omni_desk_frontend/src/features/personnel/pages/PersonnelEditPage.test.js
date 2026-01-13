import React from 'react';
import moment from 'moment';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { Form } from 'antd';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { message } from 'antd';
import PersonnelEditPage from './PersonnelEditPage';
import * as personnelApi from '../api/personnelApi';

// Mock external dependencies
jest.mock('../api/personnelApi');
jest.mock('antd', () => ({
  ...jest.requireActual('antd'),
  message: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));
// Mock child components
jest.mock('../components', () => ({
  ProfessionalQualificationTable: () => <div data-testid="pq-table-mock" />,
  PublicHousingInfoTable: () => <div data-testid="phi-table-mock" />,
  BankAccountTable: () => <div data-testid="ba-table-mock" />,
  FamilyMemberTable: () => <div data-testid="fm-table-mock" />,
}));

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  useParams: () => ({ id: '1' }),
}));


const mockPersonnelDetail = {
  data: {
    id: 1,
    name: 'Jane Doe',
    id_card_number: '12345',
    date_of_birth: '1990-01-01',
    phone_number: '555-1234',
    address: '123 Main St',
    department: 'Engineering',
    position: { id: 1, name: 'Senior Developer' },
    hire_date: '2020-03-15',
    status: 'active',
    contracts: [{ id: 1, contract_number: 'C001', contract_type: 'permanent', start_date: '2020-03-15', end_date: '2025-03-14' }],
    educations: [],
    work_experiences: [],
  }
};

const mockPositions = [{ id: 1, name: 'Senior Developer' }, { id: 2, name: 'Junior Developer' }];

const renderWithRouter = (ui) => {
  return render(
    <MemoryRouter initialEntries={['/control-panel/personnel/1/edit']}>
      <Routes>
        <Route path="/control-panel/personnel/:id/edit" element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

describe('PersonnelEditPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    personnelApi.getPersonnelDetails.mockResolvedValue(mockPersonnelDetail);
    personnelApi.updatePersonnel.mockResolvedValue({ data: {} });
    personnelApi.getAllPositions.mockResolvedValue(mockPositions);
  });

  test('shows loading spinner initially and then displays data', async () => {
    renderWithRouter(<PersonnelEditPage />);
    expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Jane Doe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('12345')).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
  });

  test('shows error message if fetching data fails', async () => {
    personnelApi.getPersonnelDetails.mockRejectedValue(new Error('Failed to fetch'));
    renderWithRouter(<PersonnelEditPage />);
    expect(await screen.findByText('获取页面数据失败')).toBeInTheDocument();
  });

  test('allows user to edit a field and submit the form', async () => {
    renderWithRouter(<PersonnelEditPage />);
    const nameInput = await screen.findByDisplayValue('Jane Doe');
    
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Jane Smith');
    
    await userEvent.click(screen.getByRole('button', { name: /保存更改/i }));

    await waitFor(() => {
      expect(personnelApi.updatePersonnel).toHaveBeenCalledWith('1', expect.objectContaining({
        name: 'Jane Smith',
      }));
      expect(message.success).toHaveBeenCalledWith('更新成功');
      expect(mockNavigate).toHaveBeenCalledWith('/control-panel/personnel');
    });
  });

  test('allows adding a new contract and submitting', async () => {
    renderWithRouter(<PersonnelEditPage />);
    await screen.findByDisplayValue('Jane Doe'); // Wait for load

    await userEvent.click(screen.getByRole('button', { name: /添加合同/i }));

    const contractNumberInput = await screen.findByPlaceholderText('合同编号');
    await userEvent.type(contractNumberInput, 'C002');
    
    // Note: antd DatePicker inputs are complex. We'll just check the submission data.
    await userEvent.click(screen.getByRole('button', { name: /保存更改/i }));

    await waitFor(() => {
      expect(personnelApi.updatePersonnel).toHaveBeenCalledWith('1', expect.objectContaining({
        contracts: expect.arrayContaining([
          expect.objectContaining({ contract_number: 'C001' }),
          expect.objectContaining({ contract_number: 'C002' }),
        ]),
      }));
    });
  });

  test('shows error message on submission failure', async () => {
    personnelApi.updatePersonnel.mockRejectedValue(new Error('Update failed'));
    renderWithRouter(<PersonnelEditPage />);
    await screen.findByDisplayValue('Jane Doe');

    const submitButton = screen.getByRole('button', { name: /保存更改/i });
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
      expect(message.error).toHaveBeenCalledWith('操作失败');
    });
  });
});