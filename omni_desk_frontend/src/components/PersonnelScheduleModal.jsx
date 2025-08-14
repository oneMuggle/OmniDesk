import React, { useState, useEffect } from 'react';
import './styles/PersonnelScheduleModal.css'; // Assuming this will be renamed to PersonnelScheduleModal.css
import { Modal, Form, Input, Button, Select, message } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { scheduleApi } from '../api/schedule';

const { Option } = Select;

/**
 * 人员排班模态框组件 - 专门用于展示人员排班信息
 */
const PersonnelScheduleModal = ({
  open,
  onCancel,
  scheduleData,
  personnelList,
  mode = 'view' // 强制为查看模式
}) => {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!form) return;
    
    if (scheduleData) {
      form.setFieldsValue({
        date: scheduleData.date,
        staff: scheduleData.staff,
        leader: scheduleData.leader
      });
    } else {
      form.resetFields();
    }
  }, [scheduleData, form]);

  const getPersonName = (id) => {
    if (!Array.isArray(personnelList)) {
      console.warn('personnelList is not an array:', personnelList);
      return '未知人员';
    }
    const person = personnelList.find(p => p.id === id);
    return person ? person.name : '未知人员';
  };

  return (
    <>
    <Modal
      title="排班详情"
      open={open}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          关闭
        </Button>
      ]}
    >
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
                  <span>{(Array.isArray(personnelList) && personnelList.find(p => p.id === scheduleData?.staff)?.phone) || '无电话'}</span>
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
                  <span>{(Array.isArray(personnelList) && personnelList.find(p => p.id === scheduleData?.leader)?.phone) || '无电话'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
    </Modal>
  </>
  );
};

export default PersonnelScheduleModal;