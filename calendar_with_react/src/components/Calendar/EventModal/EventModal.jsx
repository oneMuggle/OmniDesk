import React, { useState, useEffect } from 'react';
import { Button, Form, Modal } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import TrialSelector from './TrialSelector';
import TimeSlotForm from './TimeSlotForm';
import TrialDetails from './TrialDetails';
import { fromServerFormat, toServerFormat, formatDate } from '../../../utils/dateUtils';
import dayjs from 'dayjs';

const EventModal = ({ isGuest: propsIsGuest = false,
  currentEvent,
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
    console.log('[DEBUG] EventModal - useEffect triggered. currentEvent.id:', currentEvent?.id, 'selectedTrial.id:', selectedTrial?.id);

    if (currentEvent?.extendedProps?.trialDetails) {
      // 如果事件中已经包含试验详情，直接使用
      const trial = currentEvent.extendedProps.trialDetails;
      form.setFieldsValue({ trial: trial.id });
      setSelectedTrial(trial);
      
      calendarApi.fetchTimeSlotsByTrial(trial.id)
        .then(slots => {
          if (!slots || slots.length === 0) {
            console.warn('获取到空时间段数组', { trialId: trial.id });
            form.setFieldsValue({ time_slots: [] });
            return;
          }
          
          console.log('[DEBUG] EventModal - 原始时间段数据:', slots);
          const validSlots = slots.filter(slot =>
            slot.id && (slot.start || slot.start_time) && (slot.end || slot.end_time)
          );
          
          if (validSlots.length !== slots.length) {
            console.warn('EventModal - 过滤掉无效时间段', {
              trialId: trial.id,
              total: slots.length,
              valid: validSlots.length
            });
          }
          
          const mappedTimeSlots = validSlots.map(slot => {
            const startValue = slot.start_time ? fromServerFormat(slot.start_time) : (slot.start ? dayjs(slot.start) : null);
            const endValue = slot.end_time ? fromServerFormat(slot.end_time) : (slot.end ? dayjs(slot.end) : null);
            
            console.log(`[DEBUG] EventModal (Mapping) - Slot ID: ${slot.id}, original start: ${slot.start}, original end: ${slot.end}, original start_time: ${slot.start_time}, original end_time: ${slot.end_time}`);
            console.log(`[DEBUG] EventModal (Mapping) - Slot ID: ${slot.id}, mapped timeRange Start: ${startValue?.format() || 'null'}, End: ${endValue?.format() || 'null'}`);
            console.log(`[DEBUG] EventModal (Mapping) - Slot ID: ${slot.id}, timeRange Start valid: ${startValue?.isValid()}, End valid: ${endValue?.isValid()}`);
            
            return {
              id: slot.id,
              dateRange: [startValue, endValue], // 日期部分
              timeOnlyRange: [startValue, endValue], // 时间部分
              description: slot.description || ''
            };
          });
          console.log('[DEBUG] EventModal (Before setFieldsValue) - mappedTimeSlots:', JSON.stringify(mappedTimeSlots, (key, value) => {
            if (value && typeof value === 'object' && typeof value.isValid === 'function' && value.isValid()) {
              return value.format(); // Convert dayjs objects to string for logging
            }
            return value;
          }, 2));
          form.setFieldsValue({ time_slots: mappedTimeSlots });
        })
        .catch(error => {
          console.error('获取时间段失败:', error);
          Modal.warning({
            title: '获取时间段失败',
            content: `无法获取试验 ${trial.title} 的时间段数据`,
          });
          form.setFieldsValue({ time_slots: [] });
        });
    } else if (currentEvent?.trialId) {
      // 如果只有trialId，则从trials数组中查找
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
              slot.id && (slot.start || slot.start_time) && (slot.end || slot.end_time)
            );
            
            if (validSlots.length !== slots.length) {
              console.warn('EventModal - 过滤掉无效时间段 (trialId分支)', {
                trialId: trial.id,
                total: slots.length,
                valid: validSlots.length
              });
            }
            
            const mappedTimeSlots = validSlots.map(slot => {
              const startValue = slot.start_time ? fromServerFormat(slot.start_time) : (slot.start ? dayjs(slot.start) : null);
              const endValue = slot.end_time ? fromServerFormat(slot.end_time) : (slot.end ? dayjs(slot.end) : null);
              
              return {
                id: slot.id,
                dateRange: [startValue, endValue], // 日期部分
                timeOnlyRange: [startValue, endValue], // 时间部分
                description: slot.description || ''
              };
            });
            form.setFieldsValue({ time_slots: mappedTimeSlots });
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
        console.log('处理时间段', slot);
        const [startDate, endDate] = slot.dateRange || [null, null];
        const [startTimeOnly, endTimeOnly] = slot.timeOnlyRange || [null, null];

        if (!startDate || !endDate || !startTimeOnly || !endTimeOnly) {
          throw new Error('所有时间段必须包含日期和时间');
        }

        const startDateTime = dayjs(startDate).hour(dayjs(startTimeOnly).hour()).minute(dayjs(startTimeOnly).minute());
        const endDateTime = dayjs(endDate).hour(dayjs(endTimeOnly).hour()).minute(dayjs(endTimeOnly).minute());

        if (!startDateTime.isValid() || !endDateTime.isValid() || endDateTime.isBefore(startDateTime)) {
          throw new Error('时间段无效: 结束时间必须晚于开始时间');
        }

        return {
          start_time: toServerFormat(startDateTime),
          end_time: toServerFormat(endDateTime),
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
        const start1 = fromServerFormat(slot1.start_time);
        const end1 = fromServerFormat(slot1.end_time);
        
        for (let j = i + 1; j < validSlots.length; j++) {
          const slot2 = validSlots[j];
          const start2 = fromServerFormat(slot2.start_time);
          const end2 = fromServerFormat(slot2.end_time);
          
          // 检查时间段是否重叠
          if (!(end1.isSameOrBefore(start2) || start2.isSameOrBefore(end1))) { // 使用 isSameOrBefore 避免边界问题
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
            start: toServerFormat(dayjs(slot.dateRange[0]).hour(dayjs(slot.timeOnlyRange[0]).hour()).minute(dayjs(slot.timeOnlyRange[0]).minute())),
            end: toServerFormat(dayjs(slot.dateRange[1]).hour(dayjs(slot.timeOnlyRange[1]).hour()).minute(dayjs(slot.timeOnlyRange[1]).minute())),
            description: slot.description
          }));

        // 处理修改的时间段 (有ID的)
        const modifiedTimeSlots = modifiedSlots.length > 0 
          ? validSlots
              .filter(slot => slot.id && modifiedSlots.includes(slot.id))
              .map(slot => ({
                id: slot.id,
                start_time: toServerFormat(dayjs(slot.dateRange[0]).hour(dayjs(slot.timeOnlyRange[0]).hour()).minute(dayjs(slot.timeOnlyRange[0]).minute())),
                end_time: toServerFormat(dayjs(slot.dateRange[1]).hour(dayjs(slot.timeOnlyRange[1]).hour()).minute(dayjs(slot.timeOnlyRange[1]).minute())),
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
      className="event-modal"
      title={currentEvent ? (isEditing ? '编辑排班 - 编辑模式' : '编辑排班 - 查看模式') : '新建排班'}
      open={!!currentEvent}
      onCancel={() => {
        setIsEditing(false);
        setCurrentEvent(null);
        form.resetFields();
        setSelectedTrial(null);
      }}
      closable={true}
      width={1200}
      bodyStyle={{ overflow: 'visible' }}
      footer={
        !isEditing ? [ // 当 isEditing 为 false 时
          !propsIsGuest && (
            <Button key="edit" type="primary" onClick={() => setIsEditing(true)}>
              编辑
            </Button>
          ),
          <Button key="close" onClick={() => setCurrentEvent(null)}>
            关闭
          </Button>
        ].filter(Boolean) : [ // 当 isEditing 为 true 时
          <Button key="save" type="primary" onClick={handleManualSave} disabled={propsIsGuest}>
            保存
          </Button>,
          <Button key="cancel" onClick={() => {
            setIsEditing(false);
            form.resetFields();
            setCurrentEvent(null);
          }}>
            取消
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

        {currentEvent?.extendedProps?.scheduleDetails ? (
          <div style={{ marginBottom: 24 }}>
            <h3>排班详情</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <h4>负责人信息</h4>
                <p>姓名: {currentEvent.extendedProps.scheduleDetails.leader.name}</p>
                <p>联系方式: {currentEvent.extendedProps.scheduleDetails.leader.contact}</p>
              </div>
              <div>
                <h4>工作人员信息</h4>
                <p>姓名: {currentEvent.extendedProps.scheduleDetails.staff.name}</p>
                <p>联系方式: {currentEvent.extendedProps.scheduleDetails.staff.contact}</p>
              </div>
              <div>
                <h4>排班信息</h4>
                <p>日期: {formatDate(currentEvent.start, 'YYYY-MM-DD')}</p>
                <p>时间: {currentEvent.extendedProps.scheduleDetails.time}</p>
              </div>
              <div>
                <h4>职位信息</h4>
                <p>职位: {currentEvent.extendedProps.scheduleDetails.position}</p>
                <p>部门: {currentEvent.extendedProps.scheduleDetails.department}</p>
              </div>
            </div>
          </div>
        ) : selectedTrial && (
          <>
            <div style={{ display: 'none' }} data-testid="selected-trial-data">
              {JSON.stringify(selectedTrial)}
            </div>
            <TrialDetails selectedTrial={selectedTrial} />
          </>
        )}

        <TimeSlotForm
          form={form}
          isEditing={isEditing}
          isGuest={propsIsGuest}
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
