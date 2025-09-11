import React, { useState, useEffect } from 'react';
import { List, Button, Modal, Form, Input, Select, message, Popconfirm, Card, Col, Row } from 'antd';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../api/sequenceApi';
import { getPersonnel, getAllPersonnel } from '../api/personnelApi';

const { Option } = Select;

const SequenceForm = ({ visible, onCancel, onSave, sequence, personnelList, isLeader }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (sequence) {
      form.setFieldsValue(sequence);
    } else {
      form.resetFields();
    }
    console.log('SequenceForm - personnelList:', personnelList);
  }, [sequence, form, personnelList]);

  const handleSave = () => {
    form.validateFields()
      .then(values => {
        onSave({ ...sequence, ...values });
        form.resetFields();
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
            placeholder="请选择人员并排序"
            optionLabelProp="label"
          >
            {personnelList.map(p => {
              console.log('SequenceForm - Rendering personnel option:', p);
              return (
                <Option key={p.id} value={p.id} label={p.name}>
                  {p.name}
                </Option>
              );
            })}
          </Select>
        </Form.Item>
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

      <SequenceForm
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onSave={handleSave}
        sequence={editingSequence}
        personnelList={allPersonnel}
        isLeader={isEditingLeader}
      />
    </>
  );
};

export default SequenceManager;