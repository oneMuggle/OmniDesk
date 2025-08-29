import React, { useEffect } from 'react';
import { Modal, Form, Input, DatePicker, Select, Button, Row, Col, Typography, Space } from 'antd';
import dayjs from 'dayjs';
import PropTypes from 'prop-types';
import { useAuth } from '../context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData'; // 引入 useScheduleData
import { useTrialScheduleData } from '../hooks/useTrialScheduleData'; // 引入 useTrialScheduleData
import { useQueryClient } from '@tanstack/react-query'; // 引入 useQueryClient
import { trialApi } from '../api/trialApi';
import { MinusCircleOutlined, PlusOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const { Option } = Select;
const { RangePicker } = DatePicker;
const { Text } = Typography;

const CalendarEventModal = ({
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
  const queryClient = useQueryClient(); // 获取 queryClient

  useEffect(() => {
    console.log('CalendarEventModal - useEffect: currentEvent', currentEvent);
    if (currentEvent) {
      console.log('CurrentEvent Type:', currentEvent.type); // New log
      console.log('CalendarEventModal - Inside useEffect, currentEvent:', currentEvent);
      console.log('CalendarEventModal - Inside useEffect, currentEvent.extendedProps:', currentEvent.extendedProps);
      console.log('CalendarEventModal - CurrentEvent Full JSON:', JSON.stringify(currentEvent, null, 2)); // New log
      if (currentEvent.extendedProps?.type === 'SCHEDULE') {
        console.log('CalendarEventModal - Inside useEffect, SCHEDULE type branch');
        form.setFieldsValue({
          duty_date: currentEvent.start ? dayjs(currentEvent.start) : null,
          duty_person: currentEvent.extendedProps?.duty_person_id,
          duty_leader: currentEvent.extendedProps?.duty_leader_id,
        });
      } else if (currentEvent.extendedProps?.type === 'TRIAL') {
        console.log('CalendarEventModal - Inside useEffect, TRIAL type branch');
        console.log('CalendarEventModal - raw time_ranges from extendedProps:', currentEvent.extendedProps?.time_ranges);
        const mappedTimeRanges = currentEvent.extendedProps?.time_ranges?.map(tr => {
          const startTime = tr.start_time ? dayjs(tr.start_time) : null;
          const endTime = tr.end_time ? dayjs(tr.end_time) : null;
          if (startTime && startTime.isValid() && endTime && endTime.isValid()) {
            return {
              id: tr.id,
              start_end_time: [startTime, endTime],
              description: tr.description,
            };
          }
          return {
            id: tr.id,
            start_end_time: [null, null],
            description: tr.description,
          };
        }) || [];
        console.log('CalendarEventModal - mappedTimeRanges:', JSON.stringify(mappedTimeRanges, null, 2));

        const fieldsToSet = {
          trial_id: currentEvent.extendedProps?.trialId,
          time_ranges: mappedTimeRanges,
          description: currentEvent.extendedProps?.description,
          status: currentEvent.extendedProps?.status,
          client: currentEvent.extendedProps?.client,
          equipment_ids: currentEvent.extendedProps?.equipment?.map(e => e.id),
          responsible_person_ids: currentEvent.extendedProps?.personnel?.map(p => p.id),
        };
        console.log('CalendarEventModal - useEffect: fieldsToSet', JSON.stringify(fieldsToSet, null, 2));
        form.setFieldsValue(fieldsToSet);
      }
      setIsEditing(!!currentEvent.id); // 如果有ID，则认为是编辑模式
    } else {
      form.resetFields();
      setIsEditing(false);
    }
  }, [currentEvent, form, setIsEditing, form.getFieldValue('time_ranges')]);

  const handleValuesChange = async (changedValues, allValues) => {
    if ('trial_id' in changedValues && changedValues.trial_id) {
      // 查找对应的试验对象
      const selectedTrialData = trials.find(
        (trial) => trial.id === changedValues.trial_id
      );

      if (selectedTrialData) {
        // 设置 title, client, description
        form.setFieldsValue({
          title: selectedTrialData.title,
          client: selectedTrialData.client,
          description: selectedTrialData.description,
        });
      }

      if (!isEditing) { // 只有在新增模式下才自动填充时间段
        try {
          const timeSlots = await trialApi.fetchTimeSlotsByTrial(changedValues.trial_id);
          const mappedTimeRanges = timeSlots.map(tr => ({
            start_end_time: [dayjs(tr.start_time), dayjs(tr.end_time)],
          }));
          form.setFieldsValue({ time_ranges: mappedTimeRanges });
        } catch (error) {
          console.error('Failed to fetch trial time slots:', error);
        }
      }
    }
  };

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const processedValues = { ...values };
        if (processedValues.time_ranges) {
          processedValues.time_slots_data = processedValues.time_ranges.map(tr => ({
            id: tr.id,
            start_time: tr.start_end_time[0].toISOString(),
            end_time: tr.start_end_time[1].toISOString(),
            description: tr.description,
          }));
          delete processedValues.time_ranges;
        }
        onSave(processedValues);
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
        name="client"
        label="客户"
        rules={[{ required: true, message: '该字段是必填项。' }]}
      >
        <Input disabled={true} />
      </Form.Item>
      <Form.Item
        name="description"
        label="描述"
        rules={[{ required: true, message: '该字段是必填项。' }]}
      >
        <Input.TextArea rows={2} disabled={true} />
      </Form.Item>
      <Form.List name="time_ranges">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, fieldKey, ...restField }) => (
              <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Form.Item
                  {...restField}
                  name={[name, 'start_end_time']}
                  fieldKey={[fieldKey, 'start_end_time']}
                  rules={[{ required: true, message: '请选择时间段!' }]}
                >
                  <RangePicker
                    key={`${name}-${form.getFieldValue(['time_ranges', name, 'start_end_time'])?.[0]?.toISOString() || ''}-${form.getFieldValue(['time_ranges', name, 'start_end_time'])?.[1]?.toISOString() || ''}`}
                    showTime={{ format: 'HH:mm' }}
                    format="YYYY-MM-DD HH:mm"
                    getPopupContainer={() => document.body}
                  />
                </Form.Item>
                <MinusCircleOutlined
                  onClick={() => remove(name)}
                />
              </Space>
            ))}
            <Form.Item>
              <Button type="dashed" onClick={() => add({ id: `new_slot_${Date.now()}` })} block icon={<PlusOutlined />}>
                添加时间段
              </Button>
            </Form.Item>
          </>
        )}
      </Form.List>

      {isEditing && (
        <>
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
        </>
      )}
      {isEditing && (
        <>
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
        </>
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
      <Text strong>时间: </Text><Text>{dayjs(currentEvent.start).format('YYYY-MM-DD HH:mm')} - {dayjs(currentEvent.end).format('YYYY-MM-DD HH:mm')}</Text><br />
      <Text strong>相关设备: </Text><Text>{currentEvent.extendedProps?.equipment?.map(e => e.name).join(', ') || 'N/A'}</Text><br />
      <Text strong>责任人: </Text><Text>{currentEvent.extendedProps?.personnel?.map(p => p.username).join(', ') || 'N/A'}</Text><br />
    </>
  );

  return (
    <Modal
      title={currentEvent && currentEvent.id ? "编辑日程" : "新增日程"}
      open={!!currentEvent}
      onOk={handleOk}
      onCancel={onCancel}
      footer={!isGuest && (!currentEvent || !currentEvent.id || isEditing) ? [
        <Button key="cancel" onClick={onCancel}>取消</Button>,
        <Button key="submit" type="primary" onClick={handleOk}>保存</Button>,
      ] : null}
    >
      <Form form={form} layout="vertical" onValuesChange={handleValuesChange}>
        {currentEvent?.extendedProps?.type === 'SCHEDULE' && (
          currentEvent.id ? (isEditing ? renderScheduleForm() : renderDetails(currentEvent.extendedProps?.scheduleDetails)) : renderScheduleForm()
        )}
        {currentEvent?.extendedProps?.type === 'TRIAL' && (
          renderTrialForm()
        )}
      </Form>
    </Modal>
  );
};

CalendarEventModal.propTypes = {
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