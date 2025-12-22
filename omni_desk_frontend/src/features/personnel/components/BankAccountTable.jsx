import PropTypes from 'prop-types';
import { Table, Button } from 'antd';

const BankAccountTable = ({ data, isEditing }) => {
  const columns = [
    { title: '开户行', dataIndex: 'bank_name', key: 'bank_name' },
    { title: '账号', dataIndex: 'account_number', key: 'account_number' },
    { title: '卡类型', dataIndex: 'card_type', key: 'card_type' },
  ];

  if (isEditing) {
    columns.push({
      title: '操作',
      key: 'action',
      render: () => (
        <span>
          <Button type="link">编辑</Button>
          <Button type="link" danger>删除</Button>
        </span>
      ),
    });
  }

  return (
    <div>
      {isEditing && (
        <Button type="primary" style={{ marginBottom: 16 }}>
          添加银行账号
        </Button>
      )}
      <Table
        dataSource={Array.isArray(data) ? data : []}
        columns={columns}
        rowKey="id"
        pagination={false}
      />
    </div>
  );
};

BankAccountTable.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  isEditing: PropTypes.bool,
};

BankAccountTable.defaultProps = {
  data: [],
  isEditing: false,
};

export default BankAccountTable;