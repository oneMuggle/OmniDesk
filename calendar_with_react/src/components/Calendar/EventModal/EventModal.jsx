import React, { useState, useEffect } from 'react';
import { Button, Form, Modal } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import TrialSelector from './TrialSelector';
import TimeSlotForm from './TimeSlotForm';
import TrialDetails from './TrialDetails';
import { fromServerFormat, toServerFormat, formatDate } from '../../../utils/dateUtils';

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
                start_time: slot.start_time || slot.start,
                end_time: slot.end_time || slot.end,
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
        const startTime = slot.start_time || slot.start;
        const endTime = slot.end_time || slot.end;
        
        if (!startTime || !endTime) {
          throw new Error('所有时间段必须包含开始和结束时间');
        }
        
        const start = fromServerFormat(startTime);
        const end = fromServerFormat(endTime);
        
        if (!start || !end || end <= start) {
          throw new Error('时间段无效: 结束时间必须晚于开始时间');
        }
        
        return {
          start_time: toServerFormat(start),
          end_time: toServerFormat(end),
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

      // 检查时间段重叠
      for (let i = 0; i < validSlots.length; i++) {
        const slot1 = validSlots[i];
        const start1 = fromServerFormat(slot1.start_time || slot1.start);
        const end1 = fromServerFormat(slot1.end_time || slot1.end);
        
        for (let j = i + 1; j < validSlots.length; j++) {
          const slot2 = validSlots[j];
          const start2 = fromServerFormat(slot2.start_time || slot2.start);
          const end2 = fromServerFormat(slot2.end_time || slot2.end);
          
          // 检查时间段是否重叠
          if (!(end1.isBefore(start2) || start2.isBefore(end1))) {
            throw new Error(`时间段重叠: ${formatDate(start1, 'YYYY-MM-DD HH:mm')}至${formatDate(end1, 'YYYY-MM-DD HH:mm')} 与 ${formatDate(start2, 'YYYY-MM-DD HH:mm')}至${formatDate(end2, 'YYYY-MM-DD HH:mm')}`);
          }
        }
      }

      // 处理时间段更新
      if (isEditing) {
        console.log('[DEBUG] 处理时间段更新', {
          validSlots,
          modifiedSlots
        });

        // 获取当前表单中所有时间段的ID列表
        const currentSlotIds = validSlots
          .filter(slot => slot.id)
          .map(slot => slot.id);
        
        // 处理新增的时间段 (没有ID的)
        const newTimeSlots = validSlots
          .filter(slot => !slot.id)
          .map(slot => ({
            start: toServerFormat(slot.start_time || slot.start),
            end: toServerFormat(slot.end_time || slot.end),
            description: slot.description
          }));

        // 处理修改的时间段 (有ID的)
        const modifiedTimeSlots = modifiedSlots.length > 0 
          ? validSlots
              .filter(slot => slot.id && modifiedSlots.includes(slot.id))
              .map(slot => ({
                id: slot.id,
                start_time: toServerFormat(slot.start_time || slot.start),
                end_time: toServerFormat(slot.end_time || slot.end),
                description: slot.description
              }))
          : [];

        console.log('[DEBUG] 时间段更新详情', {
          newTimeSlots,
          modifiedTimeSlots
        });

        // 创建新时间段
        if (newTimeSlots.length > 0) {
          console.log('[DEBUG] 创建新时间段', newTimeSlots);
          await calendarApi.bulkCreateTimeSlots(formData.trial, newTimeSlots);
        } else {
          console.log('[DEBUG] 没有新时间段需要创建');
        }
        
        // 更新修改的时间段
        if (modifiedTimeSlots.length > 0) {
          console.log('[DEBUG] 更新修改的时间段', modifiedTimeSlots);
          await Promise.all(
            modifiedTimeSlots.map(slot => {
              return calendarApi.updateTimeSlot(slot.id, slot);
            })
          );
        } else {
          console.log('[DEBUG] 没有时间段需要更新');
        }
        
        if (newTimeSlots.length > 0 || modifiedTimeSlots.length > 0) {
          queryClient.invalidateQueries(['trials']);
          setModifiedSlots([]);
        }
      }
      
      // 更新事件数据
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
          calendarApi={calendarApi}
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
