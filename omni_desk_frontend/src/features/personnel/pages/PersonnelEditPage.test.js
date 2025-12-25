import React from 'react';
import moment from 'moment';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { Form } from 'antd';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PersonnelEditPage from './PersonnelEditPage';
import * as personnelApi from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockPersonnelDetail = {
  data: {
    id: 1,
    name: 'Jane Doe',
    id_card_number: '12345',
    date_of_birth: '1990-01-01',
    phone_number: '555-1234',
    address: '123 Main St',
    department: 'Engineering',
    position: 'Senior Developer',
    hire_date: '2020-03-15',
    status: 'active',
    contracts: [{ id: 1, contract_number: 'C001', contract_type: 'permanent', start_date: '2020-03-15', end_date: '2025-03-14' }],
    educations: [{ id: 1, school: 'State University', degree: 'M.Sc.', major: 'Computer Engineering', start_date: '2016-09-01', end_date: '2018-06-15' }],
    work_experiences: [{ id: 1, company: 'Tech Corp', position: 'Developer', start_date: '2018-07-01', end_date: '2020-03-14', description: 'Developed awesome things.' }],
  }
};

const renderWithRouter = (ui, { route = '/', path = '/' } = {}) => {
  window.history.pushState({}, 'Test page', route);
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path={path} element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

describe('PersonnelEditPage', () => {
  beforeEach(() => {
    personnelApi.getPersonnelDetails.mockResolvedValue(mockPersonnelDetail);
    personnelApi.updatePersonnel.mockResolvedValue({ data: {} });
    personnelApi.getAllPositions.mockResolvedValue([]);
  });

  test('loads and displays existing personnel data', async () => {
    renderWithRouter(<PersonnelEditPage />, { route: '/control-panel/personnel/edit/1', path: '/control-panel/personnel/edit/:id' });
    await waitFor(async () => {
      expect(await screen.findByDisplayValue('Jane Doe')).toBeInTheDocument();
      expect(screen.getByDisplayValue('12345')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  test('allows adding a new contract and submitting the form', async () => {
    const formRef = React.createRef();
    renderWithRouter(<PersonnelEditPage formRef={formRef} />, { route: '/control-panel/personnel/edit/1', path: '/control-panel/personnel/edit/:id' });
    
    await waitFor(() => {
      expect(formRef.current).toBeDefined();
    });

    expect(await screen.findByDisplayValue('Jane Doe')).toBeInTheDocument();

    const testStartDate = moment();
    const testEndDate = moment().add(1, 'year');

    await act(async () => {
      const currentValues = formRef.current.getFieldsValue();
      const newContract = {
        contract_number: 'C002',
        contract_type: 'fixed-term',
        start_date: testStartDate,
        end_date: testEndDate,
      };
      formRef.current.setFieldsValue({
        contracts: [...(currentValues.contracts || []), newContract],
      });
    });
    
    await act(async () => {
      formRef.current.submit();
    });

    await waitFor(() => {
      expect(personnelApi.updatePersonnel).toHaveBeenCalledWith('1', expect.objectContaining({
        contracts: expect.arrayContaining([
          expect.objectContaining({
            contract_number: 'C002',
            contract_type: 'fixed-term',
            start_date: testStartDate.format('YYYY-MM-DD'),
            end_date: testEndDate.format('YYYY-MM-DD'),
          }),
          expect.objectContaining({
            contract_number: 'C001'
          })
        ])
      }));
    });
  });
});