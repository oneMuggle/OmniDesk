import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PersonnelDetailPage from './PersonnelDetailPage';
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

describe('PersonnelDetailPage', () => {
  it('shows loading spinner initially', () => {
    personnelApi.getPersonnelDetails.mockReturnValue(new Promise(() => {})); // Never resolves
    renderWithRouter(<PersonnelDetailPage />, { route: '/control-panel/personnel/1', path: '/control-panel/personnel/:id' });
    expect(screen.getByRole('spin')).toBeInTheDocument();
  });

  it('displays personnel details after successful fetch', async () => {
    personnelApi.getPersonnelDetails.mockResolvedValue(mockPersonnelDetail);
    renderWithRouter(<PersonnelDetailPage />, { route: '/control-panel/personnel/1', path: '/control-panel/personnel/:id' });

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument();
    expect(await screen.findByText('12345')).toBeInTheDocument();
    expect(await screen.findByText('C001')).toBeInTheDocument();
    expect(await screen.findByText('State University')).toBeInTheDocument();
    expect(await screen.findByText('Tech Corp')).toBeInTheDocument();
  });

  it('displays error message on fetch failure', async () => {
    personnelApi.getPersonnelDetails.mockRejectedValue(new Error('Failed to fetch'));
    renderWithRouter(<PersonnelDetailPage />, { route: '/control-panel/personnel/1', path: '/control-panel/personnel/:id' });

    await waitFor(() => expect(screen.queryByRole('spin')).not.toBeInTheDocument());
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
  });
});