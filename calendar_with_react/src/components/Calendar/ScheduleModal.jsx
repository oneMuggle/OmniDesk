import React, { useState, useEffect } from 'react';
import './ScheduleModal.css';
import { Modal, Form, Input, Button, Select, message } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../../api/calendar';

const { Option } = Select;

const ScheduleModal = ({
  open,
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
    if (mode !== 'edit') return;
    
    if (scheduleData) {
      form.setFieldsValue({
        date: scheduleData.date,
        staff: scheduleData.staff,
        leader: scheduleData.leader
      });
    } else {
      form.resetFields();
    }
  }, [scheduleData, mode]);

  const handleSubmit = async () => {
    if (mode !== 'edit') return;
    
    try {
      console.log('[DEBUG] 保存按钮被点击');
      setLoading(true);
      
      // 更详细的表单验证
      let values;
      try {
        values = await form.validateFields();
        console.log('[DEBUG] 表单验证通过，字段值:', values);
      } catch (validationError) {
        console.error('[DEBUG] 表单验证失败:', validationError);
        const errorFields = validationError.errorFields || [];
        const errorMessages = errorFields.map(field => field.errors.join(', ')).join('; ');
        message.error(`表单验证失败: ${errorMessages}`);
        return;
      }
      
      const date = values.date || scheduleData.date;
      
      const schedule = {
        date,
        staff: values.staff,
        leader: values.leader,
      };
      console.log('[DEBUG] 准备提交的排班数据:', schedule);
      
      // 添加API调用前检查
      console.log('[DEBUG] 准备调用API:', 
        isEditing ? 'updateSchedule' : 'createSchedule');

      try {
        if (isEditing) {
          console.log('[DEBUG] 调用updateSchedule API');
          const response = await calendarApi.updateSchedule(scheduleData.id, schedule);
          console.log('[DEBUG] API响应:', response);
          message.success('排班更新成功');
        } else {
          // 检查日期是否已存在排班
          console.log('[DEBUG] 检查排班日期是否存在');
          const existing = await calendarApi.checkScheduleDate(date);
          if (existing) {
            message.error('该日期已有排班，请选择其他日期');
            return;
          }
          console.log('[DEBUG] 调用createSchedule API');
          const response = await calendarApi.createSchedule(schedule);
          console.log('[DEBUG] API响应:', response);
          message.success('排班创建成功');
        }

        queryClient.invalidateQueries(['schedules']);
        onSave();
        onCancel();
      } catch (apiError) {
        console.error('[DEBUG] API调用失败:', apiError);
        message.error(`API调用失败: ${apiError.message}`);
      }
    } catch (error) {
      console.error('[DEBUG] 保存过程中发生错误:', error);
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
      open={open}
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
        <div className="schedule-modal">
          <div className="schedule-modal__card">
            <div className="schedule-modal__title">
              {scheduleData?.date}
            </div>
            
            <div className="schedule-modal__grid">
              <div className="schedule-modal__person-card">
                <div className="schedule-modal__person-title">
                  <span className="schedule-modal__status-dot schedule-modal__status-dot--staff"></span>
                  <span style={{ fontWeight: '600', color: '#262626' }}>值班人员</span>
                </div>
                <div className="schedule-modal__person-name">{getPersonName(scheduleData?.staff)}</div>
                <div className="schedule-modal__phone-info">
                  <span style={{ marginRight: '6px' }}>📞</span>
                  <span>{personnelList.find(p => p.id === scheduleData?.staff)?.phone || '无电话'}</span>
                </div>
              </div>

              <div className="schedule-modal__person-card">
                <div className="schedule-modal__person-title">
                  <span className="schedule-modal__status-dot schedule-modal__status-dot--leader"></span>
                  <span style={{ fontWeight: '600', color: '#262626' }}>值班领导</span>
                </div>
                <div className="schedule-modal__person-name">{getPersonName(scheduleData?.leader)}</div>
                <div className="schedule-modal__phone-info">
                  <span style={{ marginRight: '6px' }}>📞</span>
                  <span>{personnelList.find(p => p.id === scheduleData?.leader)?.phone || '无电话'}</span>
                </div>
              </div>
            </div>
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
        </Form>
      )}
    </Modal>
  );
};

export default ScheduleModal;
