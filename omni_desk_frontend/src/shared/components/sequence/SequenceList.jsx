import PropTypes from 'prop-types';
import { Card, Button, List, Popconfirm } from 'antd';

const SequenceList = ({ title, sequences, personnelList, onEdit, onDelete, onAdd, isLeader }) => (
  <Card title={title}>
    <Button type="primary" onClick={() => onAdd(isLeader)} style={{ marginBottom: 16 }}>
      新建{title}
    </Button>
    <List
      bordered
      dataSource={sequences}
      renderItem={item => {
        const personnelNames = Array.isArray(item.sequence) && Array.isArray(personnelList)
          ? item.sequence.map(id => {
              const person = personnelList.find(p => p.id === id);
              return person ? person.name : '未知';
            }).join(' → ')
          : '未设置人员';

        return (
          <List.Item
            key={item.id}
            actions={[
              <Button key="edit" type="link" onClick={() => onEdit(item, isLeader)}>编辑</Button>,
              <Popconfirm
                key="delete"
                title="确定要删除吗?"
                onConfirm={() => onDelete(item.id, isLeader)}
                okText="是"
                cancelText="否"
              >
                <Button type="link" danger>删除</Button>
              </Popconfirm>
            ]}
          >
            <List.Item.Meta
              title={item.name}
              description={personnelNames || '未设置人员'}
            />
          </List.Item>
        );
      }}
    />
  </Card>
);

SequenceList.propTypes = {
  title: PropTypes.string.isRequired,
  sequences: PropTypes.array.isRequired,
  personnelList: PropTypes.array.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onAdd: PropTypes.func.isRequired,
  isLeader: PropTypes.bool.isRequired,
};

export default SequenceList;
