import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FamilyMemberTable from './FamilyMemberTable';
import * as api from '../../api/personnelApi';

jest.mock('../../api/personnelApi');

const mockFamilyMembers = {
  data: [
    { id: 1, name: 'Spouse Name', relationship: 'Spouse', contact_number: '111', personnel: 1 },
    { id: 2, name: 'Child Name', relationship: 'Child', contact_number: '222', personnel: 1 },
  ],
};

describe('FamilyMemberTable', () => {
  beforeEach(() => {
    api.getFamilyMembers.mockResolvedValue(mockFamilyMembers);
    api.createFamilyMember.mockResolvedValue({ data: { id: 3, name: 'New Member' } });
    api.updateFamilyMember.mockResolvedValue({ data: { id: 1, name: 'Updated Member' } });
    api.deleteFamilyMember.mockResolvedValue({});
  });

  test('renders family members fetched from API', async () => {
    render(<FamilyMemberTable personnelId={1} />);

    expect(api.getFamilyMembers).toHaveBeenCalledWith(1);
    expect(await screen.findByText('Spouse Name')).toBeInTheDocument();
    expect(await screen.findByText('Child Name')).toBeInTheDocument();
  });

  test('opens add modal, creates a new family member, and refreshes the table', async () => {
    render(<FamilyMemberTable personnelId={1} />);

    fireEvent.click(screen.getByText('添加家庭成员'));

    await waitFor(() => {
        expect(screen.getByLabelText('姓名')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: 'New Member' } });
    fireEvent.change(screen.getByLabelText('关系'), { target: { value: 'Parent' } });
    fireEvent.change(screen.getByLabelText('联系电话'), { target: { value: '333' } });

    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(api.createFamilyMember).toHaveBeenCalledWith({
        name: 'New Member',
        relationship: 'Parent',
        contact_number: '333',
        personnel: 1,
      });
    });
    expect(api.getFamilyMembers).toHaveBeenCalledTimes(2);
  });

  test('opens edit modal, updates a family member, and refreshes the table', async () => {
    render(<FamilyMemberTable personnelId={1} />);

    await screen.findByText('Spouse Name');
    fireEvent.click(screen.getAllByText('编辑')[0]);

    await waitFor(() => {
        expect(screen.getByLabelText('姓名')).toHaveValue('Spouse Name');
    });

    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: 'Updated Member' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(api.updateFamilyMember).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Member' }));
    });
    expect(api.getFamilyMembers).toHaveBeenCalledTimes(2);
  });

  test('deletes a family member and refreshes the table', async () => {
    render(<FamilyMemberTable personnelId={1} />);

    await screen.findByText('Spouse Name');
    fireEvent.click(screen.getAllByText('删除')[0]);

    await waitFor(() => {
      expect(api.deleteFamilyMember).toHaveBeenCalledWith(1);
    });
    expect(api.getFamilyMembers).toHaveBeenCalledTimes(2);
  });
});