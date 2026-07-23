import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import EquipmentPage from '../../features/equipment/pages/EquipmentPage';
import {
  getEquipment,
  createEquipment,
  updateEquipment,
  deleteEquipment,
} from '../../features/equipment/api/equipment';

jest.mock('../../features/equipment/api/equipment');

const mockEquipment = {
  data: [
    { id: 1, name: 'Microscope', description: 'For viewing small things' },
    { id: 2, name: 'Centrifuge', description: 'For separating samples' },
  ],
};

describe('EquipmentPage', () => {
  beforeEach(() => {
    getEquipment.mockResolvedValue(mockEquipment);
    createEquipment.mockResolvedValue({});
    updateEquipment.mockResolvedValue({});
    deleteEquipment.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the component and fetches equipment', async () => {
    render(<EquipmentPage />);

    expect(screen.getByRole('heading', { name: /试验设备管理/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(getEquipment).toHaveBeenCalled();
    });

    await screen.findByText('Microscope');
    await screen.findByText('Centrifuge');
  });

  test('adds a new piece of equipment', async () => {
    render(<EquipmentPage />);

    fireEvent.click(screen.getByRole('button', { name: /添加设备/i }));
    await screen.findByRole('dialog', { name: /新增设备/i });

    fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Incubator' } });
    fireEvent.change(screen.getByLabelText('设备简介'), { target: { value: 'For growing cultures' } });
    fireEvent.click(screen.getByRole('button', { name: /确认添加/i }));

    await waitFor(() => {
      expect(createEquipment).toHaveBeenCalledWith({ name: 'Incubator', description: 'For growing cultures' });
    });
  });

  test('edits an existing piece of equipment', async () => {
    render(<EquipmentPage />);

    await screen.findByText('Microscope');
    const editButtons = await screen.findAllByRole('button', { name: /编辑/i });
    fireEvent.click(editButtons[0]);

    await screen.findByRole('dialog', { name: /编辑设备/i });
    expect(screen.getByLabelText('设备名称')).toHaveValue('Microscope');

    fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Updated Microscope' } });
    fireEvent.click(screen.getByRole('button', { name: /保存修改/i }));

    await waitFor(() => {
      expect(updateEquipment).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Microscope' }));
    });
  });

  test('deletes an existing piece of equipment', async () => {
    render(<EquipmentPage />);

    await screen.findByText('Microscope');
    const deleteButtons = await screen.findAllByRole('button', { name: /删除/i });
    fireEvent.click(deleteButtons[0]);

    // No confirmation modal in this component, it deletes directly
    await waitFor(() => {
      expect(deleteEquipment).toHaveBeenCalledWith(1);
    });
  });
});