import { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { List, Button, Modal, Form, Input, Select, Tag, Col, Row } from 'antd';
import { Droppable, Draggable } from '@hello-pangea/dnd';
import { logger } from '../../utils/logger';

const { Option } = Select;

const SequenceForm = ({
  open, onCancel, onSave, sequence = null, personnelList, isLeader, positions,
  selectedPersonnel, setSelectedPersonnel
}) => {
  const [form] = Form.useForm();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPosition, setSelectedPosition] = useState(null);

  useEffect(() => {
    if (open) {
      if (sequence) {
        form.setFieldsValue({ name: sequence.name });
        const initialPersonnel = (sequence.sequence || [])
          .map(id => personnelList.find(p => p.id === id))
          .filter(Boolean);
        setSelectedPersonnel(initialPersonnel);
      } else {
        form.resetFields();
        setSelectedPersonnel([]);
      }
    }
  }, [open, sequence, personnelList, form, setSelectedPersonnel]);

  const handleSave = async () => {
    const values = await form.validateFields();
    const personnel_ids = selectedPersonnel.map(p => p.id);
    onSave({ ...sequence, ...values, sequence: personnel_ids });
  };

  const handleAddPersonnel = (person) => {
    if (!selectedPersonnel.find(p => p.id === person.id)) {
      setSelectedPersonnel([...selectedPersonnel, person]);
    }
  };

  const handleRemovePersonnel = (personId) => {
    setSelectedPersonnel(selectedPersonnel.filter(p => p.id !== personId));
  };

  const availablePersonnel = useMemo(() => {
    return personnelList.filter(p => {
      const name = p.name || '';
      const pinyin = p.pinyin || '';
      const lowerCaseSearchTerm = searchTerm.toLowerCase();
      const matchesSearch = name.toLowerCase().includes(lowerCaseSearchTerm) || pinyin.toLowerCase().includes(lowerCaseSearchTerm);
      const matchesPosition = !selectedPosition || p.position === selectedPosition;
      return matchesSearch && matchesPosition;
    });
  }, [personnelList, searchTerm, selectedPosition]);

  return (
    <Modal
      title={sequence ? `编辑${isLeader ? '领导' : '人员'}顺序` : `新建${isLeader ? '领导' : '人员'}顺序`}
      open={open}
      onCancel={onCancel}
      onOk={() => {
       handleSave().catch(info => {
         logger.debug('Validate Failed:', info);
       });
     }}
      width={1000}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="顺序名称" rules={[{ required: true, message: '请输入顺序名称!' }]}>
          <Input />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <h3>选择人员</h3>
            <Input
              placeholder="按姓名或拼音搜索"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ marginBottom: '10px' }}
            />
            <Select
              placeholder="按职位筛选"
              style={{ width: '100%', marginBottom: '10px' }}
              onChange={(value) => setSelectedPosition(value)}
              allowClear
            >
              {positions.map(pos => (
                <Option key={pos.id} value={pos.id}>{pos.name}</Option>
              ))}
            </Select>
            <List
              header={<div>人员列表</div>}
              bordered
              dataSource={availablePersonnel}
              renderItem={item => (
                <List.Item key={item.id} actions={[<Button key={`add-${item.id}`} type="link" onClick={() => handleAddPersonnel(item)}>添加</Button>]}>
                  {item.name} <Tag>{item.position_name}</Tag>
                </List.Item>
              )}
              style={{ height: '350px', overflowY: 'auto' }}
            />
          </Col>
          <Col span={12}>
            <h3>人员排序</h3>
            <Droppable droppableId="droppable-list">
              {(provided) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  data-testid="sorted-personnel-list"
                  style={{
                    height: '430px',
                    overflowY: 'auto',
                    border: '1px solid #d9d9d9',
                    borderRadius: '2px',
                    padding: '8px',
                    backgroundColor: '#f5f5f5'
                  }}
                >
                  {selectedPersonnel.map((item, index) => (
                    <Draggable key={item.id} draggableId={String(item.id)} index={index}>
                      {(provided, snapshot) => (
                        <div
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                          style={{
                            userSelect: 'none',
                            padding: '10px',
                            margin: '0 0 8px 0',
                            backgroundColor: snapshot.isDragging ? '#e6f7ff' : 'white',
                            border: '1px solid #d9d9d9',
                            borderRadius: '4px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            ...provided.draggableProps.style,
                          }}
                        >
                          <div>
                            <span style={{ fontWeight: 'bold' }}>{item.name}</span>
                            <Tag style={{ marginLeft: '8px' }}>{item.position_name}</Tag>
                          </div>
                          <Button
                            type="text"
                            danger
                            size="small"
                            onClick={() => handleRemovePersonnel(item.id)}
                            icon={<span style={{ fontSize: '14px' }}>✖</span>}
                          />
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
};

SequenceForm.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired,
  sequence: PropTypes.object,
  personnelList: PropTypes.array.isRequired,
  isLeader: PropTypes.bool.isRequired,
  positions: PropTypes.array.isRequired,
  selectedPersonnel: PropTypes.array.isRequired,
  setSelectedPersonnel: PropTypes.func.isRequired,
};

export default SequenceForm;
