/**
 * DataTable 组件测试(R5-D4 扩展)。
 *
 * 锁定既有 props 契约(向后兼容)+ 新增扩展能力:
 * - actions 列对齐(actionAlign)
 * - 自定义 rowSelection 透传
 * - extra columns(actions 列之外的尾部自定义列透传)
 */
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ConfigProvider } from 'antd';
import DataTable from '../DataTable';

const renderWithProvider = (ui) => render(<ConfigProvider>{ui}</ConfigProvider>);

const baseColumns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
];

const baseData = [
  { id: 1, name: '条目一' },
  { id: 2, name: '条目二' },
];

// antd v5 Table 会渲染隐藏的 measure 行(单元格文本与表头重复),
// 表头断言统一收敛到真实 <thead> 内查询
const getHeaderCells = (container) =>
  Array.from(container.querySelectorAll('thead th')).map((th) => th.textContent);

describe('DataTable 向后兼容', () => {
  it('渲染 columns 与 dataSource', () => {
    const { container } = renderWithProvider(
      <DataTable columns={baseColumns} dataSource={baseData} />
    );
    expect(getHeaderCells(container)).toContain('名称');
    expect(screen.getAllByText('条目一').length).toBeGreaterThan(0);
    expect(screen.getAllByText('条目二').length).toBeGreaterThan(0);
  });

  it('默认渲染内置操作列(onEdit + onDelete)', () => {
    const onEdit = jest.fn();
    const onDelete = jest.fn();
    const { container } = renderWithProvider(
      <DataTable columns={baseColumns} dataSource={baseData} onEdit={onEdit} onDelete={onDelete} />
    );
    expect(getHeaderCells(container)).toContain('操作');
    fireEvent.click(screen.getAllByText('编辑')[0]);
    expect(onEdit).toHaveBeenCalledWith(baseData[0]);
    fireEvent.click(screen.getAllByText('删除')[0]);
    expect(onDelete).toHaveBeenCalledWith(baseData[0]);
  });

  it('showActions=false 时不渲染操作列', () => {
    const { container } = renderWithProvider(
      <DataTable columns={baseColumns} dataSource={baseData} showActions={false} onEdit={jest.fn()} />
    );
    expect(getHeaderCells(container)).not.toContain('操作');
  });

  it('自定义 editText/deleteText 生效', () => {
    renderWithProvider(
      <DataTable
        columns={baseColumns}
        dataSource={baseData}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        editText="修改"
        deleteText="移除"
      />
    );
    // measure 行会复制一份文本,用 length 断言存在即可
    expect(screen.getAllByText('修改').length).toBeGreaterThan(0);
    expect(screen.getAllByText('移除').length).toBeGreaterThan(0);
  });
});

describe('DataTable R5-D4 扩展', () => {
  it('actionAlign 控制操作列表头对齐(right)', () => {
    const { container } = renderWithProvider(
      <DataTable
        columns={baseColumns}
        dataSource={baseData}
        onEdit={jest.fn()}
        actionAlign="right"
      />
    );
    // antd 将 align 渲染为表头 th 的 text-align 内联样式
    const actionsTh = within(container.querySelector('thead')).getByText('操作').closest('th');
    expect(actionsTh).toHaveStyle({ textAlign: 'right' });
  });

  it('actionAlign 缺省时不设置 align(向后兼容)', () => {
    const { container } = renderWithProvider(
      <DataTable columns={baseColumns} dataSource={baseData} onEdit={jest.fn()} />
    );
    const actionsTh = within(container.querySelector('thead')).getByText('操作').closest('th');
    expect(actionsTh.style.textAlign).toBe('');
  });

  it('rowSelection 透传并支持勾选回调', () => {
    const onChange = jest.fn();
    renderWithProvider(
      <DataTable
        columns={baseColumns}
        dataSource={baseData}
        showActions={false}
        rowSelection={{ selectedRowKeys: [], onChange }}
      />
    );
    const checkboxes = screen.getAllByRole('checkbox');
    // 第一个 checkbox 是表头全选,其后是行选择框
    fireEvent.click(checkboxes[1]);
    expect(onChange).toHaveBeenCalled();
  });

  it('extraColumns 追加在操作列之后', () => {
    const { container } = renderWithProvider(
      <DataTable
        columns={baseColumns}
        dataSource={baseData}
        onEdit={jest.fn()}
        extraColumns={[
          {
            title: '备注',
            key: 'remark',
            render: (_, record) => <span data-testid={`remark-${record.id}`}>备注{record.id}</span>,
          },
        ]}
      />
    );
    expect(screen.getByTestId('remark-1')).toBeInTheDocument();
    const headers = getHeaderCells(container);
    // 操作列仍在(extra 不替代 actions),且顺序为 名称 → 操作 → 备注
    expect(headers).toEqual(['名称', '操作', '备注']);
  });

  it('extraColumns 与 showActions=false 组合时直接追加到末尾', () => {
    const { container } = renderWithProvider(
      <DataTable
        columns={baseColumns}
        dataSource={baseData}
        showActions={false}
        extraColumns={[{ title: '状态', dataIndex: 'status', key: 'status' }]}
      />
    );
    expect(getHeaderCells(container)).toEqual(['名称', '状态']);
  });

  it('loading=true 时 emptyText 为空、loading=false 时显示暂无数据(锁定内建行为)', () => {
    const { rerender } = renderWithProvider(
      <DataTable columns={baseColumns} dataSource={[]} loading />
    );
    expect(screen.queryByText('暂无数据')).not.toBeInTheDocument();

    rerender(<ConfigProvider><DataTable columns={baseColumns} dataSource={[]} /></ConfigProvider>);
    expect(screen.getByText('暂无数据')).toBeInTheDocument();
  });
});
