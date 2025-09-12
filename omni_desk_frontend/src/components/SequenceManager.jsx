import React, { useState, useEffect } from 'react';
import { List, Button, Modal, Form, Input, Select, message, Popconfirm, Card, Col, Row, Tag } from 'antd';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../api/sequenceApi';
import { getPersonnel, getAllPersonnel } from '../api/personnelApi';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

const { Option } = Select;

const reorder = (list, startIndex, endIndex) => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);
  return result;
};

const SequenceForm = ({ visible, onCancel, onSave, sequence, personnelList, isLeader, onDragEnd, selectedPersonnelIds, setSelectedPersonnelIds }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) { // Only set fields when modal becomes visible
      form.setFieldsValue(sequence);
      setSelectedPersonnelIds(sequence?.sequence || []);
    } else {
      form.resetFields();
      setSelectedPersonnelIds([]);
    }
  }, [sequence, form, visible, setSelectedPersonnelIds]);


  const handleSelectChange = (values) => {
    setSelectedPersonnelIds(values);
    form.setFieldsValue({ sequence: values });
  };

  const handleSave = () => {
    form.validateFields()
      .then(values => {
        onSave({ ...sequence, ...values, sequence: selectedPersonnelIds });
        form.resetFields();
        setSelectedPersonnelIds([]);
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  return (
    <Modal
      title={sequence ? `编辑${isLeader ? '领导' : '人员'}顺序` : `新建${isLeader ? '领导' : '人员'}顺序`}
      visible={visible}
      onCancel={onCancel}
      onOk={handleSave}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="顺序名称" rules={[{ required: true, message: '请输入顺序名称!' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="sequence" label="选择人员" rules={[{ required: true, message: '请至少选择一名人员!' }]}>
          <Select
            mode="multiple"
            placeholder="请选择人员"
            onChange={handleSelectChange}
            value={selectedPersonnelIds} // Controlled component
            filterOption={(input, option) =>
              option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
          >
            {personnelList.map(p => (
              <Option key={p.id} value={p.id}>{p.name}</Option>
            ))}
          </Select>
        </Form.Item>

        {selectedPersonnelIds.length > 0 && (
          <Form.Item label="拖动排序">
              <Droppable droppableId="droppable">
                {(provided) => (
                  <div
                    {...provided.droppableProps}
                    ref={provided.innerRef}
                    style={{ border: '1px solid #d9d9d9', padding: '8px', borderRadius: '4px' }}
                  >
                    {selectedPersonnelIds.map((id, index) => {
                      const person = personnelList.find(p => p.id === id);
                      // Only render draggable if person is found to avoid errors
                      if (!person) return null;
                      return (
                        <Draggable key={String(person.id)} draggableId={String(person.id)} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              style={{
                                userSelect: 'none',
                                padding: '8px',
                                margin: '0 0 8px 0',
                                minHeight: '30px',
                                backgroundColor: snapshot.isDragging ? '#e6f7ff' : '#f0f2f5',
                                color: 'rgba(0, 0, 0, 0.85)',
                                border: snapshot.isDragging ? '1px dashed #1890ff' : '1px solid #d9d9d9',
                                borderRadius: '4px',
                                ...provided.draggableProps.style,
                              }}
                            >
                              <Tag color="blue">{person.name}</Tag>
                            </div>
                          )}
                        </Draggable>
                      );
                    })}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
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
            actions={[
              <Button type="link" onClick={() => onEdit(item, isLeader)}>编辑</Button>,
              <Popconfirm
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

const SequenceManager = () => {
  const [personnelSequences, setPersonnelSequences] = useState([]);
  const [leaderSequences, setLeaderSequences] = useState([]);
  const [allPersonnel, setAllPersonnel] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSequence, setEditingSequence] = useState(null);
  const [isEditingLeader, setIsEditingLeader] = useState(false);
  const [globalSelectedPersonnelIds, setGlobalSelectedPersonnelIds] = useState([]); // 新增全局状态

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [personnelRes, leaderRes, personnelListRes] = await Promise.all([
        getPersonnelSequences(),
        getLeaderSequences(),
        getAllPersonnel()
      ]);
      setPersonnelSequences(Array.isArray(personnelRes?.data?.results) ? personnelRes.data.results : []);
      setLeaderSequences(Array.isArray(leaderRes?.data?.results) ? leaderRes.data.results : []);
      console.log('personnelListRes.data:', personnelListRes); // Change to personnelListRes
      setAllPersonnel(personnelListRes); // Change to personnelListRes
      console.log('allPersonnel after set:', allPersonnel);
      console.log('SequenceManager - personnelListRes:', personnelListRes);
      console.log('SequenceManager - allPersonnel:', Array.isArray(personnelListRes?.data?.results) ? personnelListRes.data.results : []);
    } catch (error) {
      message.error("数据加载失败，请刷新页面重试。");
      console.error("Failed to fetch data", error);
    }
  };

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

  const reorder = (list, startIndex, endIndex) => { // Move reorder to global scope of SequenceManager
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);
    return result;
  };

  const onDragEndGlobal = (result) => {
    console.log('onDragEndGlobal triggered:', result);
    if (!result.destination) {
      return;
    }

    const newOrder = reorder(
      globalSelectedPersonnelIds,
      result.source.index,
      result.destination.index
    );
    setGlobalSelectedPersonnelIds(newOrder);

    // Update the form field with the new order
    // This is crucial for form.validateFields to get the correct sequence
    // Use a ref to the form instance or pass it as a prop if necessary
    // For now, we assume the form in SequenceForm will pick up the prop change
    // or we might need to use form.setFieldsValue directly here,
    // which would require getting the form instance from SequenceForm.
    // Let's pass setGlobalSelectedPersonnelIds to SequenceForm for now,
    // and SequenceForm will handle setting its internal form value.
  };

  const handleSave = async (values) => {
    const isUpdate = !!values.id;
    const apiCall = isEditingLeader
      ? (isUpdate ? updateLeaderSequence : createLeaderSequence)
      : (isUpdate ? updatePersonnelSequence : createPersonnelSequence);

    try {
      const response = isUpdate ? await apiCall(values.id, values) : await apiCall(values);
      const savedSequence = response.data;
      
      message.success('保存成功');
      setIsModalVisible(false);

      if (isEditingLeader) {
        setLeaderSequences(prev =>
          isUpdate ? prev.map(s => s.id === savedSequence.id ? savedSequence : s) : [...prev, savedSequence]
        );
      } else {
        setPersonnelSequences(prev =>
          isUpdate ? prev.map(s => s.id === savedSequence.id ? savedSequence : s) : [...prev, savedSequence]
        );
      }
    } catch (error) {
      message.error('保存失败');
      console.error("Failed to save sequence", error);
    }
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

      <DragDropContext onDragEnd={onDragEndGlobal}>
        <SequenceForm
          visible={isModalVisible}
          onCancel={() => setIsModalVisible(false)}
          onSave={handleSave}
          sequence={editingSequence}
          personnelList={allPersonnel}
          isLeader={isEditingLeader}
          onDragEnd={onDragEndGlobal} // Pass down to SequenceForm if needed for internal logic
          selectedPersonnelIds={globalSelectedPersonnelIds}
          setSelectedPersonnelIds={setGlobalSelectedPersonnelIds}
        />
      </DragDropContext>
    </>
  );
};

export default SequenceManager;