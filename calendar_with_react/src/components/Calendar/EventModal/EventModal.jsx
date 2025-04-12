import React, { useState, useEffect } from 'react';
import { Button, Form, Modal } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import TrialSelector from './TrialSelector';
import TimeSlotForm from './TimeSlotForm';
import TrialDetails from './TrialDetails';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';

const EventModal = ({
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
  setSelectedTrial,
  calendarApi
}) => {
  const queryClient = useQueryClient();

  // 自动设置关联试验并获取时间段
  useEffect(() => {
    if (currentEvent?.trialId) {
      const trial = trials.find(t => t.id === currentEvent.trialId);
      if (trial) {
        form.setFieldsValue({ trial: trial.id });
        setSelectedTrial(trial);
        
        calendarApi.fetchTimeSlotsByTrial(trial.id)
          .then(slots => {
            if (!slots || slots.length === 0) {
              console.warn('获取到空时间段数组', { trialId: trial.id });
              form.setFieldsValue({ time_slots: [] });
              return;
            }
            
            const validSlots = slots.filter(slot => 
              slot.id && slot.start && slot.end
            );
            
            if (validSlots.length !== slots.length) {
              console.warn('过滤掉无效时间段', {
                trialId: trial.id,
                total: slots.length,
                valid: validSlots.length
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
          })
          .catch(error => {
            console.error('获取时间段失败:', error);
        Modal.warning({
              title: '获取时间段失败',
              content: `无法获取试验 ${trial.title} 的时间段数据`,
            });
            form.setFieldsValue({ time_slots: [] });
          });
      }
    }
  }, [currentEvent, trials]);

  const handleManualSave = async () => {
    try {
      const formValues = form.getFieldsValue(true);
      const timeSlots = formValues.time_slots || [];
      
      // 验证时间段
      const validSlots = timeSlots.map(slot => {
        if (!slot?.start || !slot?.end) {
          throw new Error('所有时间段必须包含开始和结束时间');
        }
        
        const start = fromServerFormat(slot.start);
        const end = fromServerFormat(slot.end);
        
        if (!start || !end || end <= start) {
          throw new Error('时间段无效: 结束时间必须晚于开始时间');
        }
        
        return {
          start,
          end,
          ...(slot.id && { id: slot.id }),
          description: slot.description || ''
        };
      });

      if (validSlots.length === 0) {
        throw new Error('至少需要一个有效时间段');
      }

      const formData = {
        ...currentEvent,
        ...formValues,
        time_slots: validSlots,
        version: currentEvent?.version || 0
      };

      // 检查重复时间段
      const hasDuplicates = validSlots.some((slot, index) => 
        validSlots.slice(index + 1).some(other => 
          toServerFormat(slot.start) === toServerFormat(other.start) && 
          toServerFormat(slot.end) === toServerFormat(other.end)
        )
      );
      
      if (hasDuplicates) {
        throw new Error('存在重复的时间段');
      }

      // 更新修改过的时间段
      if (isEditing && modifiedSlots.length > 0) {
        const modifiedTimeSlots = validSlots
          .filter(slot => slot.id && modifiedSlots.includes(slot.id))
          .map(slot => ({
            id: slot.id,
            start: toServerFormat(slot.start),
            end: toServerFormat(slot.end),
            description: slot.description
          }));

        if (modifiedTimeSlots.length > 0) {
          await Promise.all(
            modifiedTimeSlots.map(slot => 
              calendarApi.updateTimeSlot(slot.id, slot)
            )
          );
          queryClient.invalidateQueries(['trials']);
          setModifiedSlots([]);
        }
      }

      await handleEventSubmit(formData);
      setIsEditing(false);
    } catch (error) {
      console.error('保存失败:', error);
        Modal.error({
        title: '保存失败',
        content: error.message,
      });
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
        setSelectedTrial(null);
      }}
      closable={true}
      width={800}
      footer={
        modalType === 'view' ? (
          isEditing ? [
            <Button key="save" type="primary" onClick={handleManualSave}>
              保存
            </Button>,
            <Button key="cancel" onClick={() => {
              setIsEditing(false);
              form.resetFields();
              setCurrentEvent(null);
            }}>
              取消
            </Button>
          ] : [
            <Button key="edit" type="primary" onClick={() => setIsEditing(true)}>
              编辑
            </Button>,
            <Button key="close" onClick={() => setCurrentEvent(null)}>
              关闭
            </Button>
          ]
        ) : [
          <Button key="save" type="primary" onClick={handleManualSave}>
            保存
          </Button>,
          <Button key="close" onClick={() => setCurrentEvent(null)}>
            关闭
          </Button>
        ]
      }
    >
      <Form
        layout="vertical"
        form={form}
        initialValues={{ time_slots: [] }}
      >
        <TrialSelector
          trials={trials}
          isTrialsLoading={isTrialsLoading}
          form={form}
          onTrialSelect={setSelectedTrial}
        />

        {selectedTrial && <TrialDetails selectedTrial={selectedTrial} />}

        <TimeSlotForm
          form={form}
          isEditing={isEditing}
          modifiedSlots={modifiedSlots}
          setModifiedSlots={setModifiedSlots}
          setDefaultEvents={setDefaultEvents}
          queryClient={queryClient}
          calendarApi={calendarApi}

        />
      </Form>
    </Modal>
  );
};

export default EventModal;
