import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PersonnelDetailPage from './PersonnelDetailPage';
import * as personnelApi from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockPersonnelDetail = {
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
  educations: [{ id: 1, school: 'State University', degree: 'M.Sc.', major: 'Computer Engineering', start_date: '2016-09-01', end_date: '2018-06-15' }],
  work_experiences: [{ id: 1, company: 'Tech Corp', position: 'Developer', start_date: '2018-07-01', end_date: '2020-03-14', description: 'Developed awesome things.' }],
};

const mockedGetPersonnelDetails = jest.mocked(personnelApi.getPersonnelDetails);

const renderComponent = () => {
  return render(
    <MemoryRouter initialEntries={['/control-panel/personnel/1']}>
      <Routes>
        <Route path="/control-panel/personnel/:id" element={<PersonnelDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
};

describe('PersonnelDetailPage', () => {
  beforeEach(() => {
    mockedGetPersonnelDetails.mockClear();
  });

  it('should show loading indicator and then display details on successful fetch', async () => {
    mockedGetPersonnelDetails.mockResolvedValue(mockPersonnelDetail);
    renderComponent();

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('12345')).toBeInTheDocument();
      expect(screen.getByText('C001')).toBeInTheDocument();
      expect(screen.getByText('State University')).toBeInTheDocument();
      expect(screen.getByText('Tech Corp')).toBeInTheDocument();
    });
  });

  it('should show loading indicator and then display an error message on fetch failure', async () => {
    const errorMessage = 'Failed to fetch personnel details.';
    mockedGetPersonnelDetails.mockRejectedValue(new Error(errorMessage));
    renderComponent();

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

    await waitFor(async () => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(await screen.findByText('获取人员详细信息失败')).toBeInTheDocument();
    });
  });
});