import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Modal, Form, Input, Select, List, Button, Row, Col, Tabs, message } from 'antd';
import { getPersonnel, getPositions } from '../../../features/personnel/api/personnelApi';
import apiClient from '../../api/apiClient';
import { DragDropContext, Draggable } from '@hello-pangea/dnd';
import StrictModeDroppable from './StrictModeDroppable';

const { Option } = Select;
const PersonnelSequenceModal = ({ open = false, onCancel = () => {}, onOk = () => {}, sequence = null }) => {
  const [form] = Form.useForm();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [positions, setPositions] = useState([]);
  const [personnel, setPersonnel] = useState([]);
  const [selectedPersonnel, setSelectedPersonnel] = useState([]);
  const [selectedHolidayPersonnel, setSelectedHolidayPersonnel] = useState([]);
  const [activeTab, setActiveTab] = useState('workday');

  useEffect(() => {
    if (open) {
      getPositions()
        .then(response => setPositions(response.data || []))
        .catch(error => {
          console.error('Error fetching positions:', error);
          setPositions([
            { id: 1, name: 'Manager' },
            { id: 2, name: 'Developer' },
            { id: 3, name: 'Designer' },
          ]);
        });

      if (sequence) {
        form.setFieldsValue({ name: sequence.name });
        // eslint-disable-next-line react-hooks/exhaustive-deps
      } else {
        form.resetFields();
      }
    }
  }, [open, sequence, form]);

  useEffect(() => {
    if (sequence) {
      setSelectedPersonnel(sequence.personnel_details || []);
      setSelectedHolidayPersonnel(sequence.holiday_personnel_details || []);
    } else {
      setSelectedPersonnel([]);
      setSelectedHolidayPersonnel([]);
    }
  }, [sequence]);

  useEffect(() => {
    const fetchPersonnel = async () => {
      const params = { search: searchTerm, position_id: selectedPosition };
      try {
        const data = await getPersonnel(params);
        setPersonnel(data.data);
      } catch (error) {
        console.error('Error fetching personnel:', error);
        setPersonnel([]);
      }
    };
    fetchPersonnel();
  }, [searchTerm, selectedPosition]);

  const handleAddPersonnel = (person) => {
    const isWorkday = activeTab === 'workday';
    const targetList = isWorkday ? selectedPersonnel : selectedHolidayPersonnel;
    const setTargetList = isWorkday ? setSelectedPersonnel : setSelectedHolidayPersonnel;
    if (!targetList.find(p => p.id === person.id)) {
      setTargetList([...targetList, person]);
    }
  };

  const handleRemovePersonnel = (personId, type) => {
    const setList = type === 'workday' ? setSelectedPersonnel : setSelectedHolidayPersonnel;
    setList(prevList => prevList.filter(p => p.id !== personId));
  };

  const onDragEnd = (result, type) => {
    if (!result.destination) return;
    const list = type === 'workday' ? selectedPersonnel : selectedHolidayPersonnel;
    const setList = type === 'workday' ? setSelectedPersonnel : setSelectedHolidayPersonnel;
    const items = Array.from(list);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);
    setList(items);
  };

  const handleSave = () => {
    form.validateFields().then(values => {
      if (selectedPersonnel.length === 0) {
        message.error('“工作日人员”不能为空，请至少添加一名人员。');
        return;
      }

      const sequenceIds = selectedPersonnel.map(p => p.id);
      const holidayPersonnelIds = selectedHolidayPersonnel.map(p => p.id);
      const allPersonnelIds = [...new Set([...sequenceIds, ...holidayPersonnelIds])];

      const payload = {
        name: values.name,
        sequence: sequenceIds,
        holiday_personnel: holidayPersonnelIds,
        personnel: allPersonnelIds,
      };

      const request = sequence
        ? apiClient.put(`/api/events/personnel-sequences/${sequence.id}/`, payload)
        : apiClient.post('/api/events/personnel-sequences/', payload);

      request
        .then(() => {
          onOk();
          form.resetFields();
          setSelectedPersonnel([]);
          setSelectedHolidayPersonnel([]);
        })
        .catch(error => {
          console.error('Error saving personnel sequence:', error);
          const errorMessage = error.response?.data?.personnel?.[0] || error.response?.data?.detail || '保存失败，请检查数据。';
          message.error(errorMessage);
        });
    });
  };

  const renderDraggableList = (type, list) => (
    <DragDropContext onDragEnd={(result) => onDragEnd(result, type)}>
      <StrictModeDroppable droppableId={`droppable-${type}`}>
        {(provided) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            style={{
              display: 'flex', flexWrap: 'wrap', height: '380px', overflowY: 'auto',
              border: '1px solid #d9d9d9', borderRadius: '2px', padding: '10px', alignContent: 'flex-start'
            }}
          >
            {list.map((item, index) => (
              <Draggable key={item.id} draggableId={`${type}-${item.id}`} index={index}>
                {(provided) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.draggableProps}
                    {...provided.dragHandleProps}
                    style={{
                      userSelect: 'none', padding: '10px', backgroundColor: '#fff', border: '1px solid #d9d9d9',
                      borderRadius: '4px', textAlign: 'center', position: 'relative', minHeight: '50px',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100px',
                      margin: '0 10px 10px 0', ...provided.draggableProps.style,
                    }}
                  >
                    {item.name}
                    <Button
                      type="link"
                      danger
                      onClick={() => handleRemovePersonnel(item.id, type)}
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
      </StrictModeDroppable>
    </DragDropContext>
  );

  const tabItems = [
    {
      key: 'workday',
      label: '工作日人员',
      children: renderDraggableList('workday', selectedPersonnel),
    },
    {
      key: 'holiday',
      label: '节假日人员',
      children: renderDraggableList('holiday', selectedHolidayPersonnel),
    },
  ];

  return (
    <Modal
      title={sequence ? "编辑人员顺序" : "新建人员顺序"}
      open={open}
      onOk={handleSave}
      onCancel={onCancel}
      width={1000}
      destroyOnClose
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
            data-testid="position-filter-select"
            getPopupContainer={triggerNode => triggerNode.parentNode}
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
                key={item.id}
                actions={[<Button key={`add-${item.id}`} type="link" onClick={() => handleAddPersonnel(item)}>添加</Button>]}
              >
                {item.name}
              </List.Item>
            )}
            style={{ height: '350px', overflowY: 'auto' }}
          />
        </Col>
        <Col span={12}>
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        </Col>
      </Row>
    </Modal>
  );
};

PersonnelSequenceModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onOk: PropTypes.func.isRequired,
  sequence: PropTypes.object,
};

export default PersonnelSequenceModal;