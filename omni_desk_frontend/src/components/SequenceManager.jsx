import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { List, Button, Modal, Form, Input, Select, message, Popconfirm, Card, Col, Row, Tag } from 'antd';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../api/sequenceApi';
import { getAllPersonnel, getPositions } from '../api/personnelApi';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

const { Option } = Select;

const SequenceForm = ({
  open, onCancel, onSave, sequence, personnelList, isLeader, positions,
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
         console.log('Validate Failed:', info);
       });
     }}
      width={1000}
      destroyOnClose
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
                <List.Item key={item.id} actions={[<Button type="link" onClick={() => handleAddPersonnel(item)}>添加</Button>]}>
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

SequenceForm.defaultProps = {
  sequence: null,
};

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

const SequenceManager = () => {
  const [personnelSequences, setPersonnelSequences] = useState([]);
  const [leaderSequences, setLeaderSequences] = useState([]);
  const [allPersonnel, setAllPersonnel] = useState([]);
  const [positions, setPositions] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSequence, setEditingSequence] = useState(null);
  const [isEditingLeader, setIsEditingLeader] = useState(false);
  const [selectedPersonnelInModal, setSelectedPersonnelInModal] = useState([]);

  const fetchData = React.useCallback(async () => {
    try {
      const [personnelRes, leaderRes, personnelListRes, positionsRes] = await Promise.all([
        getPersonnelSequences(),
        getLeaderSequences(),
        getAllPersonnel(),
        getPositions()
      ]);
      setPersonnelSequences(Array.isArray(personnelRes?.data?.results) ? personnelRes.data.results : []);
      setLeaderSequences(Array.isArray(leaderRes?.data?.results) ? leaderRes.data.results : []);
      setAllPersonnel(personnelListRes.results || []);
      setPositions(positionsRes?.results || []);
    } catch (error) {
      message.error("数据加载失败，请刷新页面重试。");
      console.error("Failed to fetch data", error);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  const handleAdd = (isLeader) => {
    setEditingSequence(null);
    setIsEditingLeader(isLeader);
    setIsModalVisible(true);
  };

  const handleEdit = (sequence, isLeader) => {
    setEditingSequence(sequence);
    setIsEditingLeader(isLeader);
    setIsModalVisible(true);
  };

  const handleDelete = async (id, isLeader) => {
    const apiCall = isLeader ? deleteLeaderSequence : deletePersonnelSequence;
    try {
      await apiCall(id);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除失败');
      console.error("Failed to delete sequence", error);
    }
  };

  const handleSave = async (values) => {
    const isUpdate = !!values.id;
    const apiCall = isEditingLeader
      ? (isUpdate ? updateLeaderSequence : createLeaderSequence)
      : (isUpdate ? updatePersonnelSequence : createPersonnelSequence);

    try {
      isUpdate ? await apiCall(values.id, values) : await apiCall(values);
      message.success('保存成功');
      setIsModalVisible(false);
      fetchData();
    } catch (error) {
      message.error('保存失败');
      console.error("Failed to save sequence", error);
    }
  };

  const onDragEnd = (result) => {
    if (!result.destination) return;
    const items = Array.from(selectedPersonnelInModal);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);
    setSelectedPersonnelInModal(items);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingSequence(null);
  };

  return (
    <>
      <Row gutter={16}>
        <Col span={12}>
          <SequenceList
            title="人员顺序"
            sequences={personnelSequences}
            personnelList={allPersonnel}
            onAdd={handleAdd}
            onEdit={handleEdit}
            onDelete={handleDelete}
            isLeader={false}
          />
        </Col>
        <Col span={12}>
          <SequenceList
            title="领导顺序"
            sequences={leaderSequences}
            personnelList={allPersonnel}
            onAdd={handleAdd}
            onEdit={handleEdit}
            onDelete={handleDelete}
            isLeader={true}
          />
        </Col>
      </Row>

      <DragDropContext onDragEnd={onDragEnd}>
        {isModalVisible && (
          <SequenceForm
            open={isModalVisible}
            onCancel={handleCancel}
            onSave={handleSave}
            sequence={editingSequence}
            personnelList={allPersonnel}
            isLeader={isEditingLeader}
            positions={positions}
            selectedPersonnel={selectedPersonnelInModal}
            setSelectedPersonnel={setSelectedPersonnelInModal}
          />
        )}
      </DragDropContext>
    </>
  );
};

export default SequenceManager;