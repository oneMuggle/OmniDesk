import React, { useState, useEffect } from 'react';
import './ScheduleModal.css';
import { Modal, Form, Input, Button, Select, message } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../../api/calendar';

const { Option } = Select;

/**
 * 人员排班模态框组件 - 专门用于展示和编辑人员排班信息
 * 功能：
 * 1. 展示值班日期（精确到天）
 * 2. 展示值班人员和值班领导信息
 * 3. 展示联系电话
 * 4. 编辑功能允许修改值班日期、值班人员和值班领导
 */
const PersonnelScheduleModal = ({
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

  const [conflictModalVisible, setConflictModalVisible] = useState(false);
  const [conflictInfo, setConflictInfo] = useState(null);
  const [pendingSchedule, setPendingSchedule] = useState(null);

  const checkScheduleConflict = async (date) => {
    try {
      const response = await calendarApi.checkScheduleDate(date);
      return response;
    } catch (error) {
      console.error('检查排班冲突失败:', error);
      return false;
    }
  };

  const handleSubmit = async () => {
    if (mode !== 'edit') return;
    
    try {
      setLoading(true);
      const values = await form.validateFields();
      
      // 检查是否有实际修改
      if (isEditing) {
        const originalValues = {
          date: scheduleData.date,
          staff: scheduleData.staff,
          leader: scheduleData.leader
        };
        
        if (values.date === originalValues.date &&
            values.staff === originalValues.staff &&
            values.leader === originalValues.leader) {
          message.info('没有修改内容');
          return;
        }
      }
      
      const schedule = {
        date: values.date || scheduleData.date,
        staff: values.staff,
        leader: values.leader,
      };

      // 检查排班冲突
      const hasConflict = await checkScheduleConflict(schedule.date);
      if (hasConflict && !isEditing) {
        setConflictInfo({
          date: schedule.date,
          message: `该日期(${schedule.date})已有排班记录`
        });
        setPendingSchedule(schedule);
        setConflictModalVisible(true);
        return;
      }

      // 使用新的upsert API
      const response = await calendarApi.upsertSchedule({
        id: isEditing ? scheduleData.id : undefined,
        ...schedule
      });
      
      message.success(isEditing ? '排班更新成功' : '排班创建成功');
      queryClient.invalidateQueries(['schedules']);
      onSave();
      onCancel();
    } catch (error) {
      console.error('[DEBUG] 保存过程中发生错误:', error);
      if (error.response?.data?.duty_date) {
        message.error(`排班冲突: ${error.response.data.duty_date.join(', ')}`);
      } else {
        message.error('操作失败: ' + (error.message || '请检查网络连接后重试'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleConflictConfirm = async (override) => {
    try {
      setLoading(true);
      
      // 确保日期格式正确
      const formattedSchedule = {
        ...pendingSchedule,
        date: typeof pendingSchedule.date === 'string' ? 
              pendingSchedule.date : 
              pendingSchedule.date[0], // 如果意外是数组，取第一个元素
        override // 告诉后端是否覆盖
      };
      
      console.log('[DEBUG] 发送的排班数据:', formattedSchedule);
      
      const response = await calendarApi.upsertSchedule(formattedSchedule);
      
      message.success('排班创建成功');
      queryClient.invalidateQueries(['schedules']);
      onSave();
      onCancel();
    } catch (error) {
      message.error('操作失败: ' + (error.message || '请检查网络连接后重试'));
    } finally {
      setLoading(false);
      setConflictModalVisible(false);
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
    <>
    <Modal
      title={mode === 'view' ? '排班详情' : (isEditing ? '编辑排班' : '新建排班')}
      open={open}
      onCancel={onCancel}
      footer={mode === 'view' ? [
        <Button key="delete" danger onClick={handleDelete} loading={loading}>
          删除
        </Button>,
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

    <Modal
      title="排班冲突"
      open={conflictModalVisible}
      onCancel={() => setConflictModalVisible(false)}
      footer={[
        <Button key="cancel" onClick={() => setConflictModalVisible(false)}>
          取消
        </Button>,
        <Button 
          key="override" 
          type="primary" 
          danger
          onClick={() => handleConflictConfirm(true)}
          loading={loading}
        >
          覆盖排班
        </Button>
      ]}
    >
      <div style={{ padding: '20px' }}>
        <p>{conflictInfo?.message}</p>
        <p>您想要如何处理这个冲突？</p>
        <p>选择"覆盖排班"将替换现有的排班记录。</p>
      </div>
    </Modal>
  </>
  );
};

export default PersonnelScheduleModal;
