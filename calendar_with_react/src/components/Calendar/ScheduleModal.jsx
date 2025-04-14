import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Select, message } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../../api/calendar';

const { Option } = Select;

const ScheduleModal = ({
  visible,
  onCancel,
  scheduleData,
  isEditing,
  personnelList,
  onSave,
  onDelete,
  mode = 'edit' // 'view' | 'edit'
}) => {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (scheduleData) {
      form.setFieldsValue({
        date: scheduleData.date,
        staff: scheduleData.staff,
        leader: scheduleData.leader,
        staffPhone: scheduleData.staffPhone,
        leaderPhone: scheduleData.leaderPhone
      });
    } else {
      form.resetFields();
    }
  }, [scheduleData, form]);

  const handleSubmit = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();
      const date = values.date || scheduleData.date;
      
      const schedule = {
        date,
        staff: values.staff,
        leader: values.leader,
        staffPhone: values.staffPhone,
        leaderPhone: values.leaderPhone
      };

      if (isEditing) {
        await calendarApi.updateSchedule(scheduleData.id, schedule);
        message.success('排班更新成功');
      } else {
        await calendarApi.createSchedule(schedule);
        message.success('排班创建成功');
      }

      queryClient.invalidateQueries(['schedules']);
      onSave();
      onCancel();
    } catch (error) {
      message.error(`操作失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    try {
      setLoading(true);
      await calendarApi.deleteSchedule(scheduleData.id);
      message.success('排班删除成功');
      queryClient.invalidateQueries(['schedules']);
      onDelete();
      onCancel();
    } catch (error) {
      message.error(`删除失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getPersonName = (id) => {
    const person = personnelList.find(p => p.id === id);
    return person ? person.name : '未知人员';
  };

  return (
    <Modal
      title={mode === 'view' ? '排班详情' : (isEditing ? '编辑排班' : '新建排班')}
      visible={visible}
      onCancel={onCancel}
      footer={mode === 'view' ? [
        <Button key="edit" type="primary" onClick={() => onSave('edit')}>
          编辑
        </Button>,
        <Button key="cancel" onClick={onCancel}>
          关闭
        </Button>
      ] : [
        isEditing && (
          <Button key="delete" danger onClick={handleDelete} loading={loading}>
            删除
          </Button>
        ),
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button 
          key="submit" 
          type="primary" 
          onClick={handleSubmit}
          loading={loading}
        >
          {isEditing ? '更新' : '保存'}
        </Button>
      ]}
    >
      {mode === 'view' ? (
        <div className="schedule-view">
          <div className="info-item">
            <label className="info-label">日期:</label>
            <span className="info-value">{scheduleData?.date}</span>
          </div>
          <div className="info-item">
            <label className="info-label">值班人员:</label>
            <span className="info-value">
              {getPersonName(scheduleData?.staff)} ({scheduleData?.staffPhone})
            </span>
          </div>
          <div className="info-item">
            <label className="info-label">值班领导:</label>
            <span className="info-value">
              {getPersonName(scheduleData?.leader)} ({scheduleData?.leaderPhone})
            </span>
          </div>
        </div>
      ) : (
        <Form form={form} layout="vertical">
          <Form.Item
            name="date"
            label="日期"
            rules={[{ required: true, message: '请选择日期' }]}
          >
            <Input disabled={isEditing} placeholder="YYYY-MM-DD" />
          </Form.Item>

          <Form.Item
            name="staff"
            label="值班人员"
            rules={[
              { required: true, message: '请选择值班人员' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('leader') !== value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('值班人和领导不能是同一人'));
                },
              }),
            ]}
          >
            <Select placeholder="选择值班人员">
              {personnelList.map(person => (
                <Option key={person.id} value={person.id}>
                  {person.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="staffPhone"
            label="值班人员电话"
            rules={[{ required: true, message: '请输入值班人员电话' }]}
          >
            <Input placeholder="输入值班人员电话" />
          </Form.Item>

          <Form.Item
            name="leader"
            label="值班领导"
            rules={[
              { required: true, message: '请选择值班领导' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('staff') !== value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('值班人和领导不能是同一人'));
                },
              }),
            ]}
          >
            <Select placeholder="选择值班领导">
              {personnelList.map(person => (
                <Option key={person.id} value={person.id}>
                  {person.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="leaderPhone"
            label="值班领导电话"
            rules={[{ required: true, message: '请输入值班领导电话' }]}
          >
            <Input placeholder="输入值班领导电话" />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
};

export default ScheduleModal;
