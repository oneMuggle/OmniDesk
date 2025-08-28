import React, { useEffect } from 'react';
import { Modal, Form, Input, DatePicker, Select, Button, Row, Col, Typography } from 'antd';
import moment from 'moment';
import PropTypes from 'prop-types';
import { useAuth } from '../context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData'; // 引入 useScheduleData
import { useTrialScheduleData } from '../hooks/useTrialScheduleData'; // 引入 useTrialScheduleData

const { Option } = Select;
const { RangePicker } = DatePicker;
const { Text } = Typography;

const CalendarEventModal = ({
  isVisible,
  currentEvent,
  onCancel,
  onSave,
  onDelete,
  onSwap,
  form,
  isEditing,
  setIsEditing,
  selectedTrial, // 用于试验日程的详情展示
}) => {
  const { isGuest } = useAuth();
  const { personnel } = useScheduleData(); // 获取人员数据
  const { trials } = useTrialScheduleData(); // 获取试验数据

  useEffect(() => {
    if (currentEvent) {
      if (currentEvent.type === 'SCHEDULE') {
        form.setFieldsValue({
          duty_date: currentEvent.start ? moment(currentEvent.start) : null,
          duty_person: currentEvent.extendedProps?.duty_person_id,
          duty_leader: currentEvent.extendedProps?.duty_leader_id,
        });
      } else if (currentEvent.type === 'TRIAL') {
        form.setFieldsValue({
          trial_id: currentEvent.extendedProps?.trialId,
          start_time: currentEvent.start ? moment(currentEvent.start) : null,
          end_time: currentEvent.end ? moment(currentEvent.end) : null,
          description: currentEvent.extendedProps?.description,
          status: currentEvent.extendedProps?.status,
          client: currentEvent.extendedProps?.client,
          equipment_ids: currentEvent.extendedProps?.equipment?.map(e => e.id),
          responsible_person_ids: currentEvent.extendedProps?.personnel?.map(p => p.id),
        });
      }
      setIsEditing(!!currentEvent.id); // 如果有ID，则认为是编辑模式
    } else {
      form.resetFields();
      setIsEditing(false);
    }
  }, [currentEvent, form, setIsEditing]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        onSave(values);
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  const renderScheduleForm = () => (
    <>
      <Form.Item
        name="duty_date"
        label="日期"
        rules={[{ required: true, message: '请选择日期!' }]}
      >
        <DatePicker disabled={isEditing} />
      </Form.Item>
      <Form.Item
        name="duty_person"
        label="值班人员"
        rules={[{ required: true, message: '请选择值班人员!' }]}
      >
        <Select placeholder="选择值班人员">
          {personnel.map(p => (
            <Option key={p.id} value={p.id}>{p.name}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="duty_leader"
        label="值班领导"
        rules={[{ required: true, message: '请选择值班领导!' }]}
      >
        <Select placeholder="选择值班领导">
          {personnel.map(p => (
            <Option key={p.id} value={p.id}>{p.name}</Option>
          ))}
        </Select>
      </Form.Item>
      {isEditing && (
        <Form.Item>
          <Button type="primary" danger onClick={() => onDelete(currentEvent.id)}>删除排班</Button>
        </Form.Item>
      )}
    </>
  );

  const renderTrialForm = () => (
    <>
      <Form.Item
        name="trial_id"
        label="试验项目"
        rules={[{ required: true, message: '请选择试验项目!' }]}
      >
        <Select placeholder="选择试验项目" disabled={isEditing}>
          {trials.map(trial => (
            <Option key={trial.id} value={trial.id}>{trial.title}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="time_range"
        label="时间范围"
        rules={[{ required: true, message: '请选择时间范围!' }]}
      >
        <RangePicker
          showTime={{ format: 'HH:mm' }}
          format="YYYY-MM-DD HH:mm"
          disabled={isEditing}
          value={[
            form.getFieldValue('start_time') ? moment(form.getFieldValue('start_time')) : null,
            form.getFieldValue('end_time') ? moment(form.getFieldValue('end_time')) : null,
          ]}
          onChange={(dates) => {
            form.setFieldsValue({
              start_time: dates ? dates[0] : null,
              end_time: dates ? dates[1] : null,
            });
          }}
        />
      </Form.Item>
      <Form.Item
        name="description"
        label="描述"
      >
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item
        name="status"
        label="状态"
      >
        <Select placeholder="选择状态">
          <Option value="pending">待定</Option>
          <Option value="in_progress">进行中</Option>
          <Option value="completed">已完成</Option>
          <Option value="cancelled">已取消</Option>
        </Select>
      </Form.Item>
      <Form.Item
        name="client"
        label="客户"
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="equipment_ids"
        label="相关设备"
      >
        <Select mode="multiple" placeholder="选择相关设备">
          {/* 这里需要提供设备的选项，目前假设没有设备API，需要根据实际情况补充 */}
          <Option value="1">设备 A</Option>
          <Option value="2">设备 B</Option>
        </Select>
      </Form.Item>
      <Form.Item
        name="responsible_person_ids"
        label="责任人"
      >
        <Select mode="multiple" placeholder="选择责任人">
          {personnel.map(p => (
            <Option key={p.id} value={p.id}>{p.name}</Option>
          ))}
        </Select>
      </Form.Item>
      {isEditing && (
        <Row gutter={16}>
          <Col span={12}>
            <Button type="primary" danger onClick={() => onDelete(currentEvent.id)} block>删除试验时间段</Button>
          </Col>
          <Col span={12}>
            <Button type="default" onClick={() => onSwap(currentEvent.id)} block>调换试验时间段</Button>
          </Col>
        </Row>
      )}
    </>
  );

  const renderDetails = (details) => (
    <>
      <Text strong>值班领导: </Text><Text>{details.leader?.name} ({details.leader?.contact})</Text><br />
      <Text strong>值班人员: </Text><Text>{details.staff?.name} ({details.staff?.contact})</Text><br />
      <Text strong>时间: </Text><Text>{details.time}</Text><br />
      <Text strong>职位: </Text><Text>{details.position}</Text><br />
      <Text strong>部门: </Text><Text>{details.department}</Text><br />
    </>
  );

  const renderTrialDetails = (details) => (
    <>
      <Text strong>试验项目: </Text><Text>{selectedTrial?.title || 'N/A'}</Text><br />
      <Text strong>描述: </Text><Text>{details?.description || 'N/A'}</Text><br />
      <Text strong>状态: </Text><Text>{details?.status || 'N/A'}</Text><br />
      <Text strong>客户: </Text><Text>{details?.client || 'N/A'}</Text><br />
      <Text strong>时间: </Text><Text>{moment(currentEvent.start).format('YYYY-MM-DD HH:mm')} - {moment(currentEvent.end).format('YYYY-MM-DD HH:mm')}</Text><br />
      <Text strong>相关设备: </Text><Text>{currentEvent.extendedProps?.equipment?.map(e => e.name).join(', ') || 'N/A'}</Text><br />
      <Text strong>责任人: </Text><Text>{currentEvent.extendedProps?.personnel?.map(p => p.username).join(', ') || 'N/A'}</Text><br />
    </>
  );

  return (
    <Modal
      title={currentEvent ? (isEditing ? "编辑日程" : "查看日程详情") : "新增日程"}
      open={isVisible}
      onOk={handleOk}
      onCancel={onCancel}
      footer={!isGuest && isEditing ? [
        <Button key="cancel" onClick={onCancel}>取消</Button>,
        <Button key="submit" type="primary" onClick={handleOk}>保存</Button>,
      ] : null}
    >
      <Form form={form} layout="vertical">
        {currentEvent?.type === 'SCHEDULE' && (
          isEditing ? renderScheduleForm() : renderDetails(currentEvent.extendedProps?.scheduleDetails)
        )}
        {currentEvent?.type === 'TRIAL' && (
          isEditing ? renderTrialForm() : renderTrialDetails(currentEvent.extendedProps)
        )}
      </Form>
    </Modal>
  );
};

CalendarEventModal.propTypes = {
  isVisible: PropTypes.bool.isRequired,
  currentEvent: PropTypes.object,
  onCancel: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onSwap: PropTypes.func.isRequired,
  form: PropTypes.object.isRequired,
  isEditing: PropTypes.bool.isRequired,
  setIsEditing: PropTypes.func.isRequired,
  selectedTrial: PropTypes.object,
};

export default CalendarEventModal;