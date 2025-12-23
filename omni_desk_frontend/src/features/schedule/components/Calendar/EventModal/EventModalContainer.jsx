import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { scheduleApi } from '../../../api/schedule';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';
import { Modal, Button, Form } from 'antd';
import TrialSelector from './TrialSelector';
import TimeSlotForm from './TimeSlotForm';
import TrialDetails from './TrialDetails';

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
  const [userSelectedTrial, setUserSelectedTrial] = useState(null);

  const { mutateAsync: updateTimeSlots, isPending: isUpdatingTimeSlots } = useMutation({
    mutationFn: (slots) =>
      Promise.all(
        slots.map((slot) => scheduleApi.updateTimeSlot(slot.id, slot))
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trials'] });
      setModifiedSlots([]);
    },
    onError: (error) => {
      console.error('更新时间段失败:', error);
      Modal.error({ title: '更新失败', content: '无法保存时间段更改。' });
    }
  });

  const derivedInitialTrial = useMemo(() => {
    if (currentEvent?.trialId) {
      return trials.find(t => t.id === currentEvent.trialId) || null;
    }
    return null;
  }, [currentEvent, trials]);

  const localSelectedTrial = userSelectedTrial || derivedInitialTrial;

  const fetchAndSetTimeSlots = useCallback(async (trial) => {
    if (!trial || !trial.id) {
      form.setFieldsValue({ time_slots: [] });
      return;
    }

    try {
      const slots = await scheduleApi.fetchTimeSlotsByTrial(trial.id);
      const validSlots = slots?.filter(slot => slot.id && slot.start && slot.end) || [];
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
  }, [form]);


  useEffect(() => {
    if (localSelectedTrial) {
      form.setFieldsValue({ trial: localSelectedTrial.id });
      fetchAndSetTimeSlots(localSelectedTrial);
    } else {
      form.setFieldsValue({ trial: undefined, time_slots: [] });
    }
  }, [localSelectedTrial, form, fetchAndSetTimeSlots]);

  const handleManualSave = async () => {
    try {
      await form.validateFields();
    } catch (error) {
      Modal.error({ title: '验证失败', content: '请填写所有必填项。' });
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
        if (!start.isValid() || !end.isValid() || end.isSameOrBefore(start)) {
          invalidSlots.push(`时间段 ${index + 1}: 时间无效或结束时间不晚于开始时间`);
          return null;
        }
        return { ...slot, start, end };
      } catch (e) {
        invalidSlots.push(`时间段 ${index + 1}: 时间格式解析错误`);
        return null;
      }
    }).filter(Boolean);

    if (invalidSlots.length > 0) {
      Modal.error({ title: '验证失败', content: invalidSlots.join('\n') });
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
        const modifiedTimeSlotsData = validSlots
          .filter(slot => slot.id && modifiedSlots.includes(slot.id))
          .map(slot => ({
            id: slot.id,
            start: toServerFormat(slot.start),
            end: toServerFormat(slot.end),
            description: slot.description
          }));

        if (modifiedTimeSlotsData.length > 0) {
          await updateTimeSlots(modifiedTimeSlotsData);
        }
      }
      
      await handleEventSubmit(formData);
      setIsEditing(false);
    } catch (error) {
      // Error is handled by useMutation's onError or handleEventSubmit's own try/catch
      console.error('保存事件失败:', error);
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
        setUserSelectedTrial(null);
      }}
      closable={true}
      width={800}
      footer={[
        !isEditing ? (
          <Button key="edit" type="primary" onClick={() => setIsEditing(true)}>
            编辑
          </Button>
        ) : (
          <Button key="save" type="primary" onClick={handleManualSave} loading={isUpdatingTimeSlots}>
            保存
          </Button>
        ),
        <Button 
          key="cancel" 
          onClick={() => {
            setIsEditing(false);
            form.resetFields();
            setCurrentEvent(null);
            setUserSelectedTrial(null);
          }}
        >
          {isEditing ? '取消' : '关闭'}
        </Button>
      ]}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Form layout="vertical" form={form} initialValues={{ time_slots: [{ id: 'new_slot', start: null, end: null, description: '' }] }}>
          <TrialSelector
            trials={trials}
            isTrialsLoading={isTrialsLoading}
            form={form}
            scheduleApi={scheduleApi}
            Modal={Modal}
            onTrialSelect={(trial) => {
              setUserSelectedTrial(trial);
              setSelectedTrial(trial);
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
            scheduleApi={scheduleApi}
            Modal={Modal}
          />
        </Form>
      </div>
    </Modal>
  );
};

export default EventModalContainer;
