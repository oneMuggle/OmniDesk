import PropTypes from 'prop-types';
import { Table, Button } from 'antd';

const PublicHousingInfoTable = ({ data, isEditing }) => {
  const columns = [
    { title: '门牌号', dataIndex: 'house_number', key: 'house_number' },
    { title: '房屋地址', dataIndex: 'address', key: 'address' },
    { title: '房屋类型', dataIndex: 'house_type', key: 'house_type' },
    { title: '房屋面积', dataIndex: 'area', key: 'area' },
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
          添加公房信息
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

PublicHousingInfoTable.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  isEditing: PropTypes.bool,
};

PublicHousingInfoTable.defaultProps = {
  data: [],
  isEditing: false,
};

export default PublicHousingInfoTable;