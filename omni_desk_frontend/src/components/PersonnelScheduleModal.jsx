import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import './styles/PersonnelScheduleModal.css'; // Assuming this will be renamed to PersonnelScheduleModal.css
import { Modal, Form, Button } from 'antd';

/**
 * 人员排班模态框组件 - 专门用于展示人员排班信息
 */
const PersonnelScheduleModal = ({
  open,
  onCancel,
  scheduleData
}) => {
  const [form] = Form.useForm();

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
                <div className="schedule-modal__person-name">{scheduleData?.staffName || '未知人员'}</div>
                <div className="schedule-modal__phone-info">
                  <span style={{ marginRight: '6px' }}>📞</span>
                  <span>{scheduleData?.staffPhone || '无电话'}</span>
                </div>
              </div>

              <div className="schedule-modal__person-card">
                <div className="schedule-modal__person-title">
                  <span className="schedule-modal__status-dot schedule-modal__status-dot--leader"></span>
                  <span style={{ fontWeight: '600', color: '#262626' }}>值班领导</span>
                </div>
                <div className="schedule-modal__person-name">{scheduleData?.leaderName || '未知人员'}</div>
                <div className="schedule-modal__phone-info">
                  <span style={{ marginRight: '6px' }}>📞</span>
                  <span>{scheduleData?.leaderPhone || '无电话'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
    </Modal>
  </>
  );
};

PersonnelScheduleModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  scheduleData: PropTypes.object,
};

PersonnelScheduleModal.defaultProps = {
  scheduleData: null,
};

export default PersonnelScheduleModal;