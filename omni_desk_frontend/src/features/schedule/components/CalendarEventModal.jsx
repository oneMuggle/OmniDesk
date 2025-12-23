import { useEffect } from 'react';
import { Modal, Form, Input, DatePicker, Select, Button, Typography, Space } from 'antd';
import dayjs from 'dayjs';
import PropTypes from 'prop-types';
import { useAuth } from '../../auth/context/AuthContext';
import { useScheduleData } from '../hooks/useScheduleData'; // 引入 useScheduleData
import { useTrialScheduleData } from '../hooks/useTrialScheduleData'; // 引入 useTrialScheduleData
import { trialApi } from '../../../shared/api/trialApi';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';

const { Option } = Select;
const { RangePicker } = DatePicker;
const { Text } = Typography;

const CalendarEventModal = ({
  currentEvent,
  onCancel,
  onSave,
  onDelete,
  form,
  isEditing,
  setIsEditing,
  isProcessing,
}) => {
  const { user } = useAuth(); // 获取 user 对象
  const canEdit = user?.role === 'admin' || user?.role === 'manager'; // 判断是否有编辑权限
  const { personnel } = useScheduleData(); // 获取人员数据
  const { trials } = useTrialScheduleData(); // 获取试验数据

  useEffect(() => {
    if (currentEvent) {
      if (currentEvent.extendedProps?.type === 'SCHEDULE') {
        form.setFieldsValue({
          duty_date: currentEvent.start ? dayjs(currentEvent.start) : null,
          duty_person: currentEvent.extendedProps?.duty_person_id,
          duty_leader: currentEvent.extendedProps?.duty_leader_id,
        });
      } else if (currentEvent.extendedProps?.type === 'TRIAL') {
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

        const fieldsToSet = {
          trial_id: currentEvent.extendedProps?.trialId,
          time_ranges: mappedTimeRanges,
          description: currentEvent.extendedProps?.description,
          status: currentEvent.extendedProps?.status,
          client: currentEvent.extendedProps?.client,
          equipment_ids: currentEvent.extendedProps?.equipment?.map(e => e.id),
          responsible_person_ids: currentEvent.extendedProps?.personnel?.map(p => p.id),
        };
        form.setFieldsValue(fieldsToSet);
      }
      setIsEditing(!!currentEvent.id); // 如果有ID，则认为是编辑模式
    } else {
      form.resetFields();
      setIsEditing(false);
    }
  }, [currentEvent, form, setIsEditing]);

  const handleValuesChange = async (changedValues) => {
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
          // 移除日志：console.error('Failed to fetch trial time slots:', error);
        }
      }
    }
  };

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const processedValues = { ...values }; // 复制表单值
        if (isEditing && currentEvent?.id) { // 如果是编辑模式且存在事件ID，则添加ID
          processedValues.id = currentEvent.id;
        }

        let finalTimeSlotsData = [];

        // 如果表单中有 time_ranges，则使用表单中的数据
        if (processedValues.time_ranges && processedValues.time_ranges.length > 0) {
          finalTimeSlotsData = processedValues.time_ranges.map(tr => {
            const startTime = tr.start_end_time && tr.start_end_time[0] ? tr.start_end_time[0].toISOString() : null;
            const endTime = tr.start_end_time && tr.start_end_time[1] ? tr.start_end_time[1].toISOString() : null;
            return {
              id: tr.id,
              start_time: startTime,
              end_time: endTime,
              description: tr.description || '', // 确保 description 不为 undefined
            };
          }).filter(slot => slot.start_time && slot.end_time); // 过滤掉 start_time 或 end_time 为 null 的时间段
        } else if (isEditing && currentEvent?.extendedProps?.time_ranges) {
          // 如果是编辑模式，且表单中没有 time_ranges，但原始事件有时间段，
          // 则保留原始时间段数据，除非用户明确删除了所有时间段（即 time_ranges 数组为空）。
          finalTimeSlotsData = currentEvent.extendedProps.time_ranges.map(tr => ({
            id: tr.id,
            start_time: tr.start_time, // 原始数据已经是 ISO 格式
            end_time: tr.end_time,     // 原始数据已经是 ISO 格式
            description: tr.description,
          }));
        } else {
          // 如果既不是表单中有 time_ranges 也不是编辑模式下有原始 time_ranges，
          // 那么 finalTimeSlotsData 应该为空，这包括新增但没有添加时间段的情况。
          finalTimeSlotsData = [];
        }

        processedValues.time_slots_data = finalTimeSlotsData;
        delete processedValues.time_ranges; // 移除原始的 time_ranges 字段

        console.log('CalendarEventModal - handleOk: processedValues', processedValues);
        onSave(processedValues);
      })
      .catch(() => {
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
        <Input disabled={!canEdit} />
      </Form.Item>
      <Form.Item
        name="description"
        label="描述"
        rules={[{ required: true, message: '该字段是必填项。' }]}
      >
        <Input.TextArea rows={2} disabled={!canEdit} />
      </Form.Item>
      <Form.List name="time_ranges">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, fieldKey, ...restField }) => (
              <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                {/* 隐藏的 id 字段 */}
                <Form.Item
                  name={[name, 'id']}
                  fieldKey={[fieldKey, 'id']}
                  hidden
                >
                  <Input />
                </Form.Item>
                <Form.Item
                  {...restField}
                  name={[name, 'start_end_time']}
                  fieldKey={[fieldKey, 'start_end_time']}
                  rules={[{ required: true, message: '请选择时间段!' }]}
                >
                  <RangePicker
                    showTime={{ format: 'HH:mm' }}
                    format="YYYY-MM-DD HH:mm"
                    getPopupContainer={() => document.body}
                    disabled={!canEdit}
                  />
                </Form.Item>
                {canEdit && ( // 只有管理员和经理可以删除时间段
                  <MinusCircleOutlined
                    onClick={() => remove(name)}
                  />
                )}
              </Space>
            ))}
            {canEdit && ( // 只有管理员和经理可以添加时间段
              <Form.Item>
                <Button type="dashed" onClick={() => add({ id: `new_slot_${Date.now()}` })} block icon={<PlusOutlined />}>
                  添加时间段
                </Button>
              </Form.Item>
            )}
          </>
        )}
      </Form.List>

      {(isEditing && canEdit) && ( // 只有在编辑模式且有编辑权限时才显示这些字段
        <>
          <Form.Item
            name="status"
            label="状态"
          >
            <Select placeholder="选择状态" disabled={!canEdit}>
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
            <Select mode="multiple" placeholder="选择相关设备" disabled={!canEdit}>
              {/* 这里需要提供设备的选项，目前假设没有设备API，需要根据实际情况补充 */}
              <Option value="1">设备 A</Option>
              <Option value="2">设备 B</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="responsible_person_ids"
            label="责任人"
          >
            <Select mode="multiple" placeholder="选择责任人" disabled={!canEdit}>
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


  return (
    <Modal
      title={currentEvent && currentEvent.id ? "编辑日程" : "新增日程"}
      open={!!currentEvent}
      onOk={handleOk}
      onCancel={onCancel}
      footer={canEdit && (!currentEvent || !currentEvent.id || isEditing) ? [ // 只有管理员和经理且在编辑或新增时才显示保存按钮
        <Button key="cancel" onClick={onCancel}>取消</Button>,
        <Button key="submit" type="primary" onClick={handleOk} loading={isProcessing}>保存</Button>,
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
  form: PropTypes.object.isRequired,
  isEditing: PropTypes.bool.isRequired,
  setIsEditing: PropTypes.func.isRequired,
  selectedTrial: PropTypes.object,
  isProcessing: PropTypes.bool,
};

export default CalendarEventModal;