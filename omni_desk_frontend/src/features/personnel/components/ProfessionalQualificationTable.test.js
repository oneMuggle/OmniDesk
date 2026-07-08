import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import ProfessionalQualificationTable from './ProfessionalQualificationTable';
import * as api from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockQualifications = {
  data: [
    { id: 1, name: 'Cert A', issuing_authority: 'Org A', issue_date: '2023-01-01', personnel: 1 },
    { id: 2, name: 'Cert B', issuing_authority: 'Org B', issue_date: '2024-01-01', personnel: 1 },
  ],
};

describe('ProfessionalQualificationTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.getQualifications.mockResolvedValue(mockQualifications);
    api.createQualification.mockResolvedValue({ data: { id: 3, name: 'New Cert' } });
    api.updateQualification.mockResolvedValue({ data: { id: 1, name: 'Updated Cert' } });
    api.deleteQualification.mockResolvedValue({});
  });

  test('renders qualifications fetched from API', async () => {
    render(<ProfessionalQualificationTable personnelId={1} />);

    await waitFor(() => {
      expect(api.getQualifications).toHaveBeenCalledWith(1);
    });

    expect(await screen.findByText('Cert A')).toBeInTheDocument();
    expect(await screen.findByText('Cert B')).toBeInTheDocument();
  });

  test('opens add modal, creates a new qualification, and refreshes the table', async () => {
    const user = userEvent.setup();
    render(<ProfessionalQualificationTable personnelId={1} />);
    expect(await screen.findByText('Cert A')).toBeInTheDocument();

    // Mock the API response for the refresh call after creation
    const newQualification = { id: 3, name: 'New Cert', issuing_authority: 'New Org', issue_date: '2025-01-01', personnel: 1 };
    api.getQualifications.mockResolvedValue({
      data: [...mockQualifications.data, newQualification],
    });

    await user.click(screen.getByRole('button', { name: '添加职业资质' }));

    await user.type(screen.getByLabelText('证书名称'), 'New Cert');
    await user.type(screen.getByLabelText('颁发机构'), 'New Org');
    await user.type(screen.getByLabelText('颁发日期'), '2025-01-01');

    await user.click(screen.getByRole('button', { name: 'OK' }));

    // Assert that the new qualification appears in the table
    expect(await screen.findByText('New Cert')).toBeInTheDocument();

    // Verify that the create API was called correctly
    await waitFor(() => {
      expect(api.createQualification).toHaveBeenCalledWith(expect.objectContaining({
        name: 'New Cert',
        issuing_authority: 'New Org',
        personnel: 1,
      }));
    });
  });

  test('opens edit modal, updates a qualification, and refreshes the table', async () => {
    const user = userEvent.setup();
    render(<ProfessionalQualificationTable personnelId={1} />);
    expect(await screen.findByText('Cert A')).toBeInTheDocument();

    // Mock the API response for the refresh call after update
    const updatedQualification = { ...mockQualifications.data[0], name: 'Updated Cert' };
    api.getQualifications.mockResolvedValue({
      data: [updatedQualification, mockQualifications.data[1]],
    });

    await user.click(screen.getAllByText('编辑')[0]);

    const nameInput = await screen.findByLabelText('证书名称');
    expect(nameInput).toHaveValue('Cert A');

    await user.clear(nameInput);
    await user.type(nameInput, 'Updated Cert');
    await user.click(screen.getByRole('button', { name: 'OK' }));

    // Assert that the table reflects the updated qualification
    expect(await screen.findByText('Updated Cert')).toBeInTheDocument();
    expect(screen.queryByText('Cert A')).not.toBeInTheDocument();

    // Verify that the update API was called correctly
    await waitFor(() => {
      expect(api.updateQualification).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Cert' }));
    });
  });

  test('deletes a qualification and refreshes the table', async () => {
    const user = userEvent.setup();
    render(<ProfessionalQualificationTable personnelId={1} />);
    expect(await screen.findByText('Cert A')).toBeInTheDocument();

    // Mock the API response for the refresh call after deletion
    api.getQualifications.mockResolvedValue({
      data: mockQualifications.data.filter(q => q.id !== 1),
    });

    await user.click(screen.getAllByText('删除')[0]);

    // Assuming a confirmation dialog, the user would confirm.
    // Since we are mocking the successful deletion and refresh,
    // we can directly check the UI outcome.

    // Assert that the qualification is removed from the table
    await waitFor(() => {
      expect(screen.queryByText('Cert A')).not.toBeInTheDocument();
    });
    // Verify the other qualification is still there
    expect(screen.getByText('Cert B')).toBeInTheDocument();

    // Verify that the delete API was called correctly
    await waitFor(() => {
      expect(api.deleteQualification).toHaveBeenCalledWith(1);
    });
  });
});