import React, { useState, useEffect } from 'react';
import { Form } from 'antd';
import { trialApi } from '../api/trialApi';
import { useAuth } from '../context/AuthContext';
import { useTrialScheduleData } from '../hooks/useTrialScheduleData';
import CalendarEventModal from './CalendarEventModal'; // 使用新的通用模态框
import TrialSchedule from './TrialSchedule';

const TrialScheduleContainer = () => {
  const [form] = Form.useForm();
  const { isGuest } = useAuth();
  const [currentEvent, setCurrentEvent] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSlots, setModifiedSlots] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const {
    trials,
    trialEvents,
    isTrialsLoading,
    queryClient: trialQueryClient
  } = useTrialScheduleData();

  useEffect(() => {
    if (!isTrialsLoading) {
      trialQueryClient.invalidateQueries(['trials']);
    }
  }, [isTrialsLoading, trialQueryClient]);

  const handleSaveTrial = async (values) => {
    const targetTrialId = values.trial_id;
    const isNewTimeSlot = !values.id; // 如果 values 中没有 id，则表示是新增时间段

    if (!targetTrialId) {
      console.error('无法确定要更新的试验项目。');
      return;
    }

    try {
      if (isNewTimeSlot) {
        // 新增时间段到现有试验
        // values.time_ranges 包含了用户在模态框中选择的新时间段
        await trialApi.bulkCreateTimeSlots(targetTrialId, values.time_ranges);
      } else {
        // 编辑现有试验或其时间段
        // 注意：这里的 values.time_ranges 应该包含所有现有和修改后的时间段
        // 因为后端 perform_update 会删除所有再重建
        const updatePayload = {
          title: values.title,
          client: values.client,
          description: values.description,
          equipment_ids: values.equipment_ids || [],
          responsible_person_ids: values.responsible_person_ids || [],
          time_slots: values.time_ranges.map(tr => ({
            id: tr.id, // 现有时间段可能带有id
            start_time: tr.start_time,
            end_time: tr.end_time,
            description: tr.description || ''
          })),
        };
        await trialApi.updateTrial(targetTrialId, updatePayload);
      }

      trialQueryClient.invalidateQueries(['trials']); // 刷新数据
      setCurrentEvent(null); // 关闭模态框
    } catch (error) {
      console.error('保存试验失败:', error);
    }
  };

  const handleEventClick = async (clickInfo) => {
    const eventObj = clickInfo.event.toPlainObject();
    const trialId = eventObj.extendedProps?.trialId;

    let trialDetails = null;
    if (trialId) {
      trialDetails = await trialApi.getTrialDetails(trialId);
      setSelectedTrial(trialDetails);
    }

    const updatedCurrentEvent = {
      ...eventObj,
      extendedProps: {
        ...eventObj.extendedProps,
        trialDetails: trialDetails,
        time_ranges: eventObj.extendedProps?.time_ranges || [{
          start_time: eventObj.start,
          end_time: eventObj.end
        }],
      },
    };
    console.log('TrialScheduleContainer - handleEventClick: updatedCurrentEvent', updatedCurrentEvent);
    setCurrentEvent(updatedCurrentEvent);
  };

  const handleDateSelect = (selectInfo) => {
    setCurrentEvent({
      title: '',
      time_ranges: [{
        start_time: selectInfo.start,
        end_time: selectInfo.end,
      }],
      allDay: selectInfo.allDay,
      extendedProps: { // 将 type 移动到 extendedProps
        type: 'TRIAL'
      }
    });
  };

  if (isTrialsLoading) {
    return <div>正在加载试验日程...</div>;
  }

  return (
    <>
      <TrialSchedule
        trials={trials}
        trialEvents={trialEvents}
        isGuest={isGuest}
        onDateClick={handleDateSelect}
        select={handleDateSelect}
        onEventClick={handleEventClick}
      />

      {currentEvent && (
        <CalendarEventModal
          isVisible={!!currentEvent}
          form={form}
          currentEvent={currentEvent}
          trials={trials}
          isGuest={isGuest}
          isEditing={isEditing}
          setIsEditing={setIsEditing}
          selectedTrial={selectedTrial}
          onSave={handleSaveTrial} // 将试验保存逻辑传递给 CalendarEventModal
          onCancel={() => setCurrentEvent(null)}
          onDelete={() => console.log('onDelete called')} // 临时空函数
          onSwap={() => console.log('onSwap called')}     // 临时空函数
        />
      )}

    </>
  );
};

export default TrialScheduleContainer;