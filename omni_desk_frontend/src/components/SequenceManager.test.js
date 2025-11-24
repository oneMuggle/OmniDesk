import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import SequenceManager from './SequenceManager';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../api/sequenceApi';
import { getAllPersonnel, getPositions } from '../api/personnelApi';

// Mock APIs
jest.mock('../api/sequenceApi');
jest.mock('../api/personnelApi');

// Mock react-beautiful-dnd
jest.mock('react-beautiful-dnd', () => ({
  ...jest.requireActual('react-beautiful-dnd'),
  DragDropContext: ({ children }) => <div>{children}</div>,
  Droppable: ({ children }) => <div>{children( { innerRef: jest.fn(), droppableProps: {}, placeholder: null } )}</div>,
  Draggable: ({ children }) => <div>{children( { innerRef: jest.fn(), draggableProps: {}, dragHandleProps: {} }, {} )}</div>,
}));


const mockPersonnelSequences = { data: { results: [{ id: 1, name: 'Personnel Seq 1', sequence: [1, 2] }] } };
const mockLeaderSequences = { data: { results: [{ id: 1, name: 'Leader Seq 1', sequence: [3] }] } };
const mockAllPersonnel = [
  { id: 1, name: 'Alice', position: 1, position_name: 'Dev' },
  { id: 2, name: 'Bob', position: 1, position_name: 'Dev' },
  { id: 3, name: 'Charlie', position: 2, position_name: 'Manager' },
];
const mockPositions = { results: [{ id: 1, name: 'Dev' }, { id: 2, name: 'Manager' }] };

describe('SequenceManager', () => {
  beforeEach(() => {
    getPersonnelSequences.mockResolvedValue(mockPersonnelSequences);
    getLeaderSequences.mockResolvedValue(mockLeaderSequences);
    getAllPersonnel.mockResolvedValue(mockAllPersonnel);
    getPositions.mockResolvedValue(mockPositions);
    createPersonnelSequence.mockResolvedValue({});
    updatePersonnelSequence.mockResolvedValue({});
    deletePersonnelSequence.mockResolvedValue({});
    createLeaderSequence.mockResolvedValue({});
    updateLeaderSequence.mockResolvedValue({});
    deleteLeaderSequence.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders and fetches initial data', async () => {
    render(<SequenceManager />);

    await waitFor(() => {
      expect(getPersonnelSequences).toHaveBeenCalled();
    });
    expect(getLeaderSequences).toHaveBeenCalled();
    expect(getAllPersonnel).toHaveBeenCalled();
    expect(getPositions).toHaveBeenCalled();

    await screen.findByText('Personnel Seq 1');
    await screen.findByText('Leader Seq 1');
  });

  test('adds a new personnel sequence', async () => {
    render(<SequenceManager />);

    const addPersonnelSeqButton = screen.getAllByRole('button', { name: /新建人员顺序/i })[0];
    fireEvent.click(addPersonnelSeqButton);

    await screen.findByRole('dialog', { name: /新建人员顺序/i });
    const nameInput = screen.getByLabelText('顺序名称');
    await fireEvent.change(nameInput, { target: { value: 'New Personnel Seq' } });
    await fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(createPersonnelSequence).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Personnel Seq' }));
    });
  });

  test('edits a leader sequence', async () => {
    render(<SequenceManager />);

    await screen.findByText('Leader Seq 1');
    const editButtons = await screen.findAllByRole('button', { name: /编辑/i });
    fireEvent.click(editButtons[1]); // Assuming second edit button is for leader sequence

    await screen.findByRole('dialog', { name: /编辑领导顺序/i });
    expect(screen.getByLabelText('顺序名称')).toHaveValue('Leader Seq 1');

    fireEvent.change(screen.getByLabelText('顺序名称'), { target: { value: 'Updated Leader Seq' } });
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(updateLeaderSequence).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Leader Seq' }));
    });
  });

  test('deletes a personnel sequence', async () => {
    render(<SequenceManager />);

    await screen.findByText('Personnel Seq 1');
    const deleteButtons = await screen.findAllByRole('button', { name: /删除/i });
    fireEvent.click(deleteButtons[0]); // Assuming first delete button is for personnel sequence

    await screen.findByText('确定要删除吗?');
    fireEvent.click(screen.getByRole('button', { name: /是/i }));

    await waitFor(() => {
      expect(deletePersonnelSequence).toHaveBeenCalledWith(1);
    });
  });

  test('adds and removes personnel in the modal', async () => {
    render(<SequenceManager />);

    const addPersonnelSeqButton = screen.getAllByRole('button', { name: /新建人员顺序/i })[0];
    fireEvent.click(addPersonnelSeqButton);

    const modal = await screen.findByRole('dialog', { name: /新建人员顺序/i });
    
    // Add Alice
    const addButtons = await within(modal).findAllByRole('button', { name: /添加/i });
    fireEvent.click(addButtons[0]); // Add Alice

    const sortedList = within(modal).getByTestId('sorted-personnel-list');
    await within(sortedList).findByText('Alice');

    // Remove Alice
    const removeButtons = await within(sortedList).findAllByRole('button', { name: /✖/i });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(within(sortedList).queryByText('Alice')).not.toBeInTheDocument();
    });
  });
});