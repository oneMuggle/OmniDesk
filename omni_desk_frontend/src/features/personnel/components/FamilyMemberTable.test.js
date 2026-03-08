import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FamilyMemberTable from './FamilyMemberTable';
import { getFamilyMembers, createFamilyMember } from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockedGetFamilyMembers = jest.mocked(getFamilyMembers);
const mockedCreateFamilyMember = jest.mocked(createFamilyMember);

describe('FamilyMemberTable', () => {
  beforeEach(() => {
    // 在每个测试前清除 mock，确保测试的独立性
    mockedGetFamilyMembers.mockClear();
    mockedCreateFamilyMember.mockClear();
  });

  it('should display family members after fetching', async () => {
    const mockFamilyMembers = [{ id: 1, name: '张三', relationship: '父亲', contact_number: '13800138000' }];
    mockedGetFamilyMembers.mockResolvedValue({ data: mockFamilyMembers });

    render(<FamilyMemberTable personnelId={1} />);

    expect(await screen.findByText('张三')).toBeInTheDocument();
  });

  it('should refresh the table with new data after adding a new family member', async () => {
    const user = userEvent.setup();
    const initialMembers = [
      { id: 1, name: '张三', relationship: '父亲', contact_number: '13800138000', personnel: 1 },
    ];
    const newMember = { id: 2, name: '王五', relationship: '儿子', contact_number: '13700137000', personnel: 1 };
    const updatedMembers = [...initialMembers, newMember];

    // 1. 初始渲染时，返回初始数据
    mockedGetFamilyMembers.mockResolvedValueOnce({ data: initialMembers });
    mockedCreateFamilyMember.mockResolvedValue({ data: newMember });

    render(<FamilyMemberTable personnelId={1} />);

    // 验证初始数据已加载
    expect(await screen.findByText('张三')).toBeInTheDocument();

    // 2. 在添加操作后，模拟下一次 getFamilyMembers 调用返回更新后的数据
    mockedGetFamilyMembers.mockResolvedValueOnce({ data: updatedMembers });

    // 点击“添加家庭成员”按钮打开模态框
    await user.click(screen.getByRole('button', { name: /添加家庭成员/i }));

    // 填写表单
    await user.type(screen.getByLabelText('姓名'), '王五');
    await user.type(screen.getByLabelText('关系'), '儿子');
    await user.type(screen.getByLabelText('联系电话'), '13700137000');

    // 点击“OK”提交
    await user.click(screen.getByRole('button', { name: 'OK' }));

    // 断言：使用 findByText 等待新成员“王五”出现在表格中
    // findBy* 查询会等待UI更新，这对于处理由非 awaited promise 引起的延迟渲染至关重要
    expect(await screen.findByText('王五')).toBeInTheDocument();
  });
});