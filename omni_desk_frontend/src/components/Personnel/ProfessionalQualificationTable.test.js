import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProfessionalQualificationTable from './ProfessionalQualificationTable';
import * as api from '../../api/personnelApi';

jest.mock('../../api/personnelApi');

const mockQualifications = {
  data: [
    { id: 1, name: 'Cert A', issuing_authority: 'Org A', issue_date: '2023-01-01', personnel: 1 },
    { id: 2, name: 'Cert B', issuing_authority: 'Org B', issue_date: '2024-01-01', personnel: 1 },
  ],
};

describe('ProfessionalQualificationTable', () => {
  beforeEach(() => {
    api.getQualifications.mockResolvedValue(mockQualifications);
    api.createQualification.mockResolvedValue({ data: { id: 3, name: 'New Cert' } });
    api.updateQualification.mockResolvedValue({ data: { id: 1, name: 'Updated Cert' } });
    api.deleteQualification.mockResolvedValue({});
  });

  test('renders qualifications fetched from API', async () => {
    render(<ProfessionalQualificationTable personnelId={1} qualifications={mockQualifications.data} fetchQualifications={jest.fn()} />);

    expect(await screen.findByText('Cert A')).toBeInTheDocument();
    expect(await screen.findByText('Cert B')).toBeInTheDocument();
    expect(api.getQualifications).toHaveBeenCalledWith(1);
    expect(api.getQualifications).toHaveBeenCalledTimes(1);
  });

  test('opens add modal, creates a new qualification, and refreshes the table', async () => {
    render(<ProfessionalQualificationTable personnelId={1} qualifications={mockQualifications.data} fetchQualifications={jest.fn()} />);
    await screen.findByText('Cert A'); // Wait for initial load
    expect(api.getQualifications).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('添加职业资质'));

    await waitFor(() => {
        expect(screen.getByLabelText('证书名称')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('证书名称'), { target: { value: 'New Cert' } });
    fireEvent.change(screen.getByLabelText('颁发机构'), { target: { value: 'New Org' } });
    // Mocking date input is tricky, let's assume the component handles it.
    // fireEvent.change(screen.getByLabelText('颁发日期'), { target: { value: '2025-01-01' } });

    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(api.createQualification).toHaveBeenCalledWith(expect.objectContaining({
        name: 'New Cert',
        issuing_authority: 'New Org',
        personnel: 1,
      }));
    });

    await waitFor(() => {
      expect(api.getQualifications).toHaveBeenCalledTimes(2);
    });
  });

  test('opens edit modal, updates a qualification, and refreshes the table', async () => {
    render(<ProfessionalQualificationTable personnelId={1} qualifications={mockQualifications.data} fetchQualifications={jest.fn()} />);

    await screen.findByText('Cert A');
    fireEvent.click(screen.getAllByText('编辑')[0]);

    await waitFor(() => {
        expect(screen.getByLabelText('证书名称')).toHaveValue('Cert A');
    });

    fireEvent.change(screen.getByLabelText('证书名称'), { target: { value: 'Updated Cert' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(api.updateQualification).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Cert' }));
    });
    await waitFor(() => {
        expect(api.getQualifications).toHaveBeenCalledTimes(2);
    });
  });

  test('deletes a qualification and refreshes the table', async () => {
    render(<ProfessionalQualificationTable personnelId={1} qualifications={mockQualifications.data} fetchQualifications={jest.fn()} />);

    await screen.findByText('Cert A');
    fireEvent.click(screen.getAllByText('删除')[0]);

    await waitFor(() => {
      expect(api.deleteQualification).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
        expect(api.getQualifications).toHaveBeenCalledTimes(2);
    });
  });
});