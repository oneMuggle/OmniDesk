import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SequenceManager from './SequenceManager';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../features/schedule/api/sequenceApi';
import { getAllPersonnel, getPositions } from '../features/personnel/api/personnelApi';

// Mock APIs
jest.mock('../features/schedule/api/sequenceApi');
jest.mock('../features/personnel/api/personnelApi');

// Mock react-beautiful-dnd
jest.mock('react-beautiful-dnd', () => {
  const PropTypes = require('prop-types');
  const DragDropContext = ({ children }) => <div>{children}</div>;
  DragDropContext.propTypes = { children: PropTypes.node.isRequired };

  const Droppable = ({ children }) => <div>{children( { innerRef: jest.fn(), droppableProps: {}, placeholder: null } )}</div>;
  Droppable.propTypes = { children: PropTypes.func.isRequired };

  const Draggable = ({ children }) => <div>{children( { innerRef: jest.fn(), draggableProps: {}, dragHandleProps: {} }, {} )}</div>;
  Draggable.propTypes = { children: PropTypes.func.isRequired };

  return {
    ...jest.requireActual('react-beautiful-dnd'),
    DragDropContext,
    Droppable,
    Draggable,
  };
});


const mockPersonnelSequences = { data: { results: [{ id: 1, name: 'Personnel Seq 1', sequence: [1, 2] }] } };
const mockLeaderSequences = { data: { results: [{ id: 1, name: 'Leader Seq 1', sequence: [3] }] } };
const mockAllPersonnel = {
  results: [
    { id: 1, name: 'Alice', position: 1, position_name: 'Dev' },
    { id: 2, name: 'Bob', position: 1, position_name: 'Dev' },
    { id: 3, name: 'Charlie', position: 2, position_name: 'Manager' },
  ],
};
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

    await screen.findByText('Personnel Seq 1');
    const addPersonnelSeqButton = screen.getByRole('button', { name: /新建人员顺序/i });
    await userEvent.click(addPersonnelSeqButton);

    const dialog = await screen.findByRole('dialog', { name: /新建人员顺序/i });
    const nameInput = within(dialog).getByLabelText('顺序名称');
    await userEvent.type(nameInput, 'New Personnel Seq');
    await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(createPersonnelSequence).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Personnel Seq' }));
    });
  });

  test('edits a leader sequence', async () => {
    render(<SequenceManager />);

    await screen.findByText('Leader Seq 1');
    const editButton = (await screen.findAllByRole('button', { name: /编辑/i }))[1];
    await userEvent.click(editButton);

    const dialog = await screen.findByRole('dialog', { name: /编辑领导顺序/i });
    const nameInput = within(dialog).getByLabelText('顺序名称');
    expect(nameInput).toHaveValue('Leader Seq 1');

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Updated Leader Seq');
    await userEvent.click(within(dialog).getByRole('button', { name: 'OK' }));

    await waitFor(() => {
      expect(updateLeaderSequence).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'Updated Leader Seq' }));
    });
  });

  test('deletes a personnel sequence', async () => {
    render(<SequenceManager />);

    await screen.findByText('Personnel Seq 1');
    const deleteButton = (await screen.findAllByRole('button', { name: /删除/i }))[0];
    await userEvent.click(deleteButton);

    await screen.findByText('确定要删除吗?');
    await userEvent.click(screen.getByRole('button', { name: /是/i }));

    await waitFor(() => {
      expect(deletePersonnelSequence).toHaveBeenCalledWith(1);
    });
  });

  test('adds and removes personnel in the modal', async () => {
    getAllPersonnel.mockResolvedValue(mockAllPersonnel.results); // Correctly return the array
    render(<SequenceManager />);

    await screen.findByText('Personnel Seq 1');
    const addPersonnelSeqButton = screen.getByRole('button', { name: /新建人员顺序/i });
    await userEvent.click(addPersonnelSeqButton);

    const modal = await screen.findByRole('dialog', { name: /新建人员顺序/i });
    
    // Add Alice
    const addButton = (await within(modal).findAllByRole('button', { name: /添加/i }))[0];
    await userEvent.click(addButton);

    const sortedList = within(modal).getByTestId('sorted-personnel-list');
    await within(sortedList).findByText('Alice');

    // Remove Alice
    const removeButton = await within(sortedList).findByRole('button', { name: /✖/i });
    await userEvent.click(removeButton);

    await waitFor(() => {
      expect(within(sortedList).queryByText('Alice')).not.toBeInTheDocument();
    });
  });
});