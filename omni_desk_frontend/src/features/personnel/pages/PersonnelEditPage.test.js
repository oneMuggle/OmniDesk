import React from 'react';
import { render, screen, waitFor, act } from '../../../test-utils';
import userEvent from '@testing-library/user-event';
import { message, Form } from 'antd';
import dayjs from 'dayjs';
import PersonnelEditPage from './PersonnelEditPage';
import * as personnelApi from '../api/personnelApi';

// Mock external dependencies
jest.mock('../api/personnelApi');
jest.mock('antd', () => {
    const antd = jest.requireActual('antd');
    return {
        ...antd,
        message: {
            success: jest.fn(),
            error: jest.fn(),
        },
    };
});

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
    ...jest.requireActual('react-router-dom'),
    useNavigate: () => mockNavigate,
    useParams: () => ({ personnelId: '1' }),
}));

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
    educations: [],
    work_experiences: [],
};

const mockPositions = [{ id: 1, name: 'Senior Developer' }, { id: 2, name: 'Junior Developer' }];

// A helper function to set up the test environment
const setupTest = async (initialData = mockPersonnelDetail) => {
    const user = userEvent.setup();
    let formInstance = null;

    // This component will capture the form instance via callback ref
    const TestWrapper = () => {
        const [form] = Form.useForm();
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const setFormRef = React.useCallback((node) => {
            if (node !== null) {
                formInstance = form;
            }
        }, [form]);
        return (
            <div ref={setFormRef}>
                <PersonnelEditPage form={form} />
            </div>
        );
    };

    render(<TestWrapper />);

    // Manually and synchronously set the form values inside an act block
    await act(async () => {
        if (initialData && formInstance) {
            formInstance.setFieldsValue({
                ...initialData,
                position: initialData.position ? initialData.position.id : null,
                date_of_birth: initialData.date_of_birth ? dayjs(initialData.date_of_birth) : null,
                hire_date: initialData.hire_date ? dayjs(initialData.hire_date) : null,
                contracts: initialData.contracts?.map(c => ({ ...c, start_date: dayjs(c.start_date), end_date: dayjs(c.end_date) })) || [],
            });
        }
    });

    return { user, form: formInstance };
};


describe('PersonnelEditPage', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        // Mock the API calls that happen inside the component's useEffect
        personnelApi.getPersonnelDetails.mockResolvedValue(mockPersonnelDetail);
        personnelApi.getAllPositions.mockResolvedValue(mockPositions);
        personnelApi.updatePersonnel.mockResolvedValue({ data: {} });
    });

    test('displays data correctly after loading', async () => {
        await setupTest();
        expect(screen.getByDisplayValue('Jane Doe')).toBeInTheDocument();
        expect(screen.getByDisplayValue('12345')).toBeInTheDocument();
    });

    test('shows error message if fetching data fails', async () => {
        // This test doesn't need the setup helper as it tests the initial load failure
        personnelApi.getPersonnelDetails.mockRejectedValue(new Error('Failed to fetch'));
        render(<PersonnelEditPage />);
        expect(await screen.findByText('获取页面数据失败')).toBeInTheDocument();
    });

    test('allows user to edit a field and submit the form', async () => {
        const { user } = await setupTest();
        const nameInput = screen.getByDisplayValue('Jane Doe');

        await user.clear(nameInput);
        await user.type(nameInput, 'Jane Smith');

        await user.click(screen.getByRole('button', { name: /保存更改/i }));

        await waitFor(() => {
            expect(personnelApi.updatePersonnel).toHaveBeenCalledWith('1', expect.objectContaining({
                name: 'Jane Smith',
            }));
        });
        expect(message.success).toHaveBeenCalledWith('更新成功');
        expect(mockNavigate).toHaveBeenCalledWith('/control-panel/personnel');
    });

    test('allows adding a new contract and submitting', async () => {
        const { user, form } = await setupTest();

        const addButton = screen.getByRole('button', { name: /添加合同/i });
        await user.click(addButton);

        const contractNumberInputs = await screen.findAllByPlaceholderText('合同编号');
        expect(contractNumberInputs).toHaveLength(2);
        const newContractNumberInput = contractNumberInputs[1];
        await user.type(newContractNumberInput, 'C002');

        // Manually set values for the new contract row to satisfy validation
        await act(async () => {
            const currentValues = form.getFieldsValue();
            const newContracts = [...currentValues.contracts];
            newContracts[1] = {
                ...newContracts[1],
                start_date: dayjs('2024-01-01'),
                end_date: dayjs('2025-01-01'),
                contract_type: 'permanent', // Also set the type
            };
            form.setFieldsValue({ contracts: newContracts });
        });

        await user.click(screen.getByRole('button', { name: /保存更改/i }));

        await waitFor(() => {
            expect(personnelApi.updatePersonnel).toHaveBeenCalledWith(
                '1',
                expect.objectContaining({
                    contracts: expect.arrayContaining([
                        expect.objectContaining({ contract_number: 'C001' }),
                        expect.objectContaining({
                            contract_number: 'C002',
                            contract_type: 'permanent',
                            start_date: '2024-01-01',
                            end_date: '2025-01-01',
                        }),
                    ]),
                })
            );
        });
    });

    test('shows error message on submission failure', async () => {
        personnelApi.updatePersonnel.mockRejectedValue(new Error('API Error'));
        const { user } = await setupTest();

        const submitButton = screen.getByRole('button', { name: /保存更改/i });
        await user.click(submitButton);

        await waitFor(() => {
            expect(message.error).toHaveBeenCalledWith('操作失败');
        });
        expect(submitButton).not.toBeDisabled();
    });
});