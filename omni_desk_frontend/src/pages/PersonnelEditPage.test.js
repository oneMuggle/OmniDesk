import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PersonnelEditPage from './PersonnelEditPage';
import * as personnelApi from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockPersonnelDetail = {
  data: {
    id: 1,
    name: 'Jane Doe',
    id_card_number: '12345',
    contracts: [],
    educations: [],
    work_experiences: [],
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
  });

  test('loads and displays existing personnel data', async () => {
    renderWithRouter(<PersonnelEditPage />, { route: '/dashboard/personnel/edit/1', path: '/dashboard/personnel/edit/:id' });
    expect(await screen.findByDisplayValue('Jane Doe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('12345')).toBeInTheDocument();
  });

  test('allows adding a new contract and submitting the form', async () => {
    renderWithRouter(<PersonnelEditPage />, { route: '/dashboard/personnel/edit/1', path: '/dashboard/personnel/edit/:id' });
    
    // Wait for initial data to load
    await screen.findByDisplayValue('Jane Doe');

    // Click "添加合同" button
    fireEvent.click(screen.getByText('添加合同'));

    // Fill in the new contract form
    fireEvent.change(screen.getByPlaceholderText('合同编号'), { target: { value: 'C002' } });
    fireEvent.change(screen.getByPlaceholderText('合同类型'), { target: { value: 'fixed-term' } });

    // Click save
    fireEvent.click(screen.getByText('保存更改'));

    // Verify the API call
    await waitFor(() => {
      expect(personnelApi.updatePersonnel).toHaveBeenCalledWith('1', expect.objectContaining({
        contracts: expect.arrayContaining([
          expect.objectContaining({
            contract_number: 'C002',
            contract_type: 'fixed-term',
          })
        ])
      }));
    });
  });
});