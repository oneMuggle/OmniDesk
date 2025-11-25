import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios';
import PersonnelSequenceModal from './PersonnelSequenceModal';

jest.mock('axios');

const mockPositions = [
  { id: 1, name: 'Manager' },
  { id: 2, name: 'Developer' },
];

const mockPersonnel = [
  { id: 1, name: 'Alice', position: 'Developer' },
  { id: 2, name: 'Bob', position: 'Manager' },
];

describe('PersonnelSequenceModal', () => {
  beforeEach(() => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/api/positions')) {
        return Promise.resolve({ data: mockPositions });
      }
      if (url.includes('/api/personnel')) {
        return Promise.resolve({ data: mockPersonnel });
      }
      return Promise.reject(new Error('not found'));
    });
    axios.post.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders the modal and fetches initial data', async () => {
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    expect(screen.getByText('新建人员顺序')).toBeInTheDocument();
    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(await screen.findByText('Bob')).toBeInTheDocument();
  });

  test('allows adding and removing personnel', async () => {
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    await waitFor(() => {
        expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByText('添加')[0]);
    
    await waitFor(() => {
        expect(screen.getAllByText('Alice').length).toBe(2);
    });

    fireEvent.click(screen.getByText('X'));
    
    await waitFor(() => {
        expect(screen.getAllByText('Alice').length).toBe(1);
    });
  });

  test('allows searching for personnel', async () => {
    axios.get.mockResolvedValue({ data: [{ id: 1, name: 'Alice', position: 'Developer' }] });
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);

    fireEvent.change(screen.getByPlaceholderText('按姓名拼音搜索'), { target: { value: 'Alice' } });

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/personnel/', { params: { search: 'Alice', position_id: null } });
    });
  });

  test('allows filtering personnel by position', async () => {
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={() => {}} />);
    
    fireEvent.mouseDown(screen.getByPlaceholderText('按职位筛选'));
    fireEvent.click(await screen.findByText('Manager'));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('/api/personnel/', { params: { search: '', position_id: 1 } });
    });
  });

  test('saves the personnel sequence', async () => {
    const onOk = jest.fn();
    render(<PersonnelSequenceModal open={true} onCancel={() => {}} onOk={onOk} />);

    await waitFor(() => {
        expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('顺序名称'), { target: { value: 'Test Sequence' } });
    fireEvent.click(screen.getAllByText('添加')[0]);
    fireEvent.click(screen.getByText('保存'));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/personnel-sequences/', {
        name: 'Test Sequence',
        personnel_ids: [1],
      });
    });
    
    await waitFor(() => {
        expect(onOk).toHaveBeenCalled();
    });
  });
});