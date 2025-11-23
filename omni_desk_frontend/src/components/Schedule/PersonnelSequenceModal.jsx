import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, List, Button, Row, Col } from 'antd';
import axios from 'axios';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

const { Option } = Select;

const PersonnelSequenceModal = ({ open, onCancel, onOk }) => {
  const [form] = Form.useForm();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [positions, setPositions] = useState([]);
  const [personnel, setPersonnel] = useState([]);
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);

  // Fetch positions from API
  useEffect(() => {
    axios.get('/api/positions/')
      .then(response => {
        setPositions(response.data);
      })
      .catch(error => {
        console.error('Error fetching positions:', error);
        // Mock data for development
        setPositions([
          { id: 1, name: 'Manager' },
          { id: 2, name: 'Developer' },
          { id: 3, name: 'Designer' },
        ]);
      });
  }, []);

  // Fetch personnel based on search and filter
  useEffect(() => {
    const params = {
      search: searchTerm,
      position_id: selectedPosition,
    };
    axios.get('/api/personnel/', { params })
      .then(response => {
        setPersonnel(response.data);
      })
      .catch(error => {
        console.error('Error fetching personnel:', error);
        // Mock data for development
        const mockPersonnel = [
          { id: 1, name: 'Alice', position: 'Developer' },
          { id: 2, name: 'Bob', position: 'Manager' },
          { id: 3, name: 'Charlie', position: 'Designer' },
          { id: 4, name: 'David', position: 'Developer' },
        ];
        let filteredData = mockPersonnel;
        if (searchTerm) {
            filteredData = filteredData.filter(p => p.name.toLowerCase().includes(searchTerm.toLowerCase()));
        }
        if (selectedPosition) {
            const posName = positions.find(p => p.id === selectedPosition)?.name;
            if (posName) {
                filteredData = filteredData.filter(p => p.position === posName);
            }
        }
        setPersonnel(filteredData);
      });
  }, [searchTerm, selectedPosition, positions]);

  const handleAddPersonnel = (person) => {
    if (!selectedPersonnel.find(p => p.id === person.id)) {
      setSelectedPersonnel([...selectedPersonnel, person]);
    }
  };

  const handleRemovePersonnel = (personId) => {
    setSelectedPersonnel(selectedPersonnel.filter(p => p.id !== personId));
  };

  const onDragEnd = (result) => {
    if (!result.destination) {
      return;
    }

    const items = Array.from(selectedPersonnel);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);

    setSelectedPersonnel(items);
  };

  const handleSave = () => {
    form.validateFields().then(values => {
      const personnelIds = selectedPersonnel.map(p => p.id);
      axios.post('/api/personnel-sequences/', { ...values, personnel_ids: personnelIds })
        .then(() => {
          onOk();
          form.resetFields();
          setSelectedPersonnel([]);
        })
        .catch(error => {
          console.error('Error saving personnel sequence:', error);
        });
    });
  };

  return (
    <Modal
      title="新建人员顺序"
      open={open}
      onOk={handleSave}
      onCancel={onCancel}
      width={1000}
      footer={[
        <Button key="back" onClick={onCancel}>
          取消
        </Button>,
        <Button key="submit" type="primary" onClick={handleSave}>
          保存
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label="顺序名称"
          rules={[{ required: true, message: '请输入顺序名称!' }]}
        >
          <Input placeholder="顺序名称" />
        </Form.Item>
      </Form>
      <Row gutter={16}>
        {/* Left Column: Select Personnel */}
        <Col span={12}>
          <h3>选择人员</h3>
          <Input
            placeholder="按姓名拼音搜索"
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
            dataSource={personnel}
            renderItem={item => (
              <List.Item
                actions={[<Button type="link" onClick={() => handleAddPersonnel(item)}>添加</Button>]}
              >
                {item.name}
              </List.Item>
            )}
            style={{ height: '350px', overflowY: 'auto' }}
          />
        </Col>

        {/* Right Column: Drag to Sort */}
        <Col span={12} style={{ display: 'flex', flexDirection: 'column' }}>
          <h3>人员排序</h3>
          <div style={{ height: '430px' }}>
            <DragDropContext onDragEnd={onDragEnd}>
              <Droppable droppableId="droppable-grid">
                {(provided) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      height: '100%',
                      overflowY: 'auto',
                      border: '1px solid #d9d9d9',
                      borderRadius: '2px',
                      padding: '10px',
                      alignContent: 'flex-start'
                    }}
                  >
                    {selectedPersonnel.map((item, index) => (
                      <Draggable key={item.id} draggableId={String(item.id)} index={index}>
                        {(provided) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            style={{
                              userSelect: 'none',
                              padding: '10px',
                              backgroundColor: '#fff',
                              border: '1px solid #d9d9d9',
                              borderRadius: '4px',
                              textAlign: 'center',
                              position: 'relative',
                              minHeight: '50px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: '100px',
                              margin: '0 10px 10px 0',
                              ...provided.draggableProps.style,
                            }}
                          >
                            {item.name}
                            <Button
                              type="link"
                              danger
                              onClick={() => handleRemovePersonnel(item.id)}
                              style={{ position: 'absolute', top: 0, right: 0, padding: '2px' }}
                            >
                              X
                            </Button>
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </DragDropContext>
          </div>
        </Col>
      </Row>
    </Modal>
  );
};

export default PersonnelSequenceModal;