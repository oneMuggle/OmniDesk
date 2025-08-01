import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../../../api/calendar';
import { getTrials } from '../../../api/trials';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';
import { Modal, Button } from 'antd';
import TrialSelector from './TrialSelector';
import TimeSlotForm from './TimeSlotForm';
import TrialDetails from './TrialDetails';
import EventModalActions from './EventModalActions';

const EventModalContainer = ({
  currentEvent,
  modalType,
  form,
  trials,
  isTrialsLoading,
  selectedTrial,
  isEditing,
  modifiedSlots,
  handleEventSubmit,
  setCurrentEvent,
  setIsEditing,
  setModifiedSlots,
  setDefaultEvents,
  setSelectedTrial
}) => {
  const queryClient = useQueryClient();
  const [localSelectedTrial, setLocalSelectedTrial] = useState(selectedTrial);

  const fetchAndSetTimeSlots = async (trial) => {
    if (!trial || !trial.id) {
      form.setFieldsValue({ time_slots: [] });
      return;
    }

    try {
      const slots = await calendarApi.fetchTimeSlotsByTrial(trial.id);
      if (!slots || slots.length === 0) {
        console.warn('获取到空时间段数组', { trialId: trial.id });
        form.setFieldsValue({ time_slots: [] });
        return;
      }

      const validSlots = slots.filter(slot => slot.id && slot.start && slot.end);
      if (validSlots.length !== slots.length) {
        console.warn('过滤掉无效时间段', {
          trialId: trial.id,
          total: slots.length,
          valid: validSlots.length,
          invalid: slots.filter(slot => !slot.id || !slot.start || !slot.end)
        });
      }

      form.setFieldsValue({
        time_slots: validSlots.map(slot => ({
          id: slot.id,
          start: slot.start,
          end: slot.end,
          description: slot.description || ''
        }))
      });
    } catch (error) {
      console.error('获取时间段失败:', error);
      Modal.warning({
        title: '获取时间段失败',
        content: `无法获取试验 ${trial.title} 的时间段数据`,
      });
      form.setFieldsValue({ time_slots: [] });
    }
  };

  useEffect(() => {
    if (currentEvent?.trialId) {
      const trial = trials.find(t => t.id === currentEvent.trialId);
      if (trial) {
        form.setFieldsValue({ trial: trial.id });
        setLocalSelectedTrial(trial);
        fetchAndSetTimeSlots(trial);
      }
    }
  }, [currentEvent, trials, form]);

  const handleManualSave = async () => {
    const trialId = form.getFieldValue('trial');
    if (!trialId) {
      Modal.error({ title: '验证失败', content: '请先选择试验项目' });
      return;
    }

    const formValues = form.getFieldsValue(true);
    const timeSlots = formValues.time_slots || [];
    
    const invalidSlots = [];
    const validSlots = timeSlots.map((slot, index) => {
      if (!slot?.start || !slot?.end) {
        invalidSlots.push(`时间段 ${index + 1}: 缺少开始或结束时间`);
        return null;
      }

      try {
        const start = fromServerFormat(slot.start);
        const end = fromServerFormat(slot.end);

        if (!start || !end || isNaN(start.toDate().getTime()) || isNaN(end.toDate().getTime())) {
          invalidSlots.push(`时间段 ${index + 1}: 时间格式无效`);
          return null;
        }

        if (end <= start) {
          invalidSlots.push(`时间段 ${index + 1}: 结束时间必须晚于开始时间`);
          return null;
        }

        return {
          start,
          end,
          ...(slot.id && { id: slot.id })
        };
      } catch (error) {
        invalidSlots.push(`时间段 ${index + 1}: ${error.message}`);
        return null;
      }
    }).filter(Boolean);

    if (invalidSlots.length > 0 || validSlots.length === 0) {
      Modal.error({
        title: '验证失败',
        content: [
          '请修正以下问题:',
          ...invalidSlots,
          validSlots.length === 0 ? '至少需要一个有效时间段' : ''
        ].join('\n'),
      });
      return;
    }

    const formData = {
      ...currentEvent,
      ...formValues,
      time_slots: validSlots,
      version: currentEvent?.version || 0
    };
    
    try {
      if (isEditing && modifiedSlots.length > 0) {
        const currentSlotIds = validSlots
          .filter(slot => slot.id)
          .map(slot => slot.id);
          
        const validModifiedSlots = modifiedSlots.filter(id => 
          currentSlotIds.includes(id)
        );
          
        const modifiedTimeSlots = formData.time_slots
          .filter(slot => 
            slot.id && 
            validModifiedSlots.includes(slot.id))
          .map(slot => ({
            id: slot.id,
            start: toServerFormat(slot.start),
            end: toServerFormat(slot.end),
            description: slot.description
          }));

        setModifiedSlots(validModifiedSlots);
      
        if (modifiedTimeSlots.length > 0) {
          await Promise.all(
            modifiedTimeSlots.map(slot => 
              calendarApi.updateTimeSlot(slot.id, slot)
            )
          );
          queryClient.invalidateQueries(['trials']);
          setModifiedSlots([]);
        }
        
        await handleEventSubmit(formData);
      } else {
        await handleEventSubmit(formData);
      }
      
      setIsEditing(false);
    } catch (error) {
      console.error('保存时间段失败:', error);
      Modal.error({ title: '保存失败', content: error.message });
    }
  };

  return (
    <Modal
      title={modalType === 'view' ? '查看试验排班' : '新建试验排班'}
      open={!!currentEvent}
      onCancel={() => {
        setIsEditing(false);
        setCurrentEvent(null);
        form.resetFields();
        setLocalSelectedTrial(null);
      }}
      closable={true}
      width={800}
      footer={[
        !isEditing ? (
          <Button key="edit" type="primary" onClick={() => setIsEditing(true)}>
            编辑
          </Button>
        ) : (
          <Button key="save" type="primary" onClick={handleManualSave}>
            保存
          </Button>
        ),
        <Button 
          key="cancel" 
          onClick={() => {
            setIsEditing(false);
            form.resetFields();
            setCurrentEvent(null);
          }}
        >
          {isEditing ? '取消' : '关闭'}
        </Button>
      ]}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <form layout="vertical" form={form} initialValues={{ time_slots: [{ id: 'new_slot', start: null, end: null, description: '' }] }}>
          <TrialSelector
            trials={trials}
            isTrialsLoading={isTrialsLoading}
            form={form}
            calendarApi={calendarApi}
            Modal={Modal}
            onTrialSelect={(trial) => {
              setLocalSelectedTrial(trial);
              setSelectedTrial(trial);
              fetchAndSetTimeSlots(trial);
            }}
          />

          {localSelectedTrial && (
            <TrialDetails selectedTrial={localSelectedTrial} />
          )}

          <TimeSlotForm
            form={form}
            isEditing={isEditing}
            modifiedSlots={modifiedSlots}
            setModifiedSlots={setModifiedSlots}
            setDefaultEvents={setDefaultEvents}
            queryClient={queryClient}
            calendarApi={calendarApi}
            Modal={Modal}
          />
        </form>
      </div>
    </Modal>
  );
};

export default EventModalContainer;
