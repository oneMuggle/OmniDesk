import { useState, useEffect } from 'react';
import { Form } from 'antd';
import { trialApi } from '../../../shared/api/trialApi';
import { useTrialScheduleData } from '../hooks/useTrialScheduleData';
import CalendarEventModal from './CalendarEventModal';
import TrialSchedule from './TrialSchedule';
import { logger } from '../../../shared/utils/logger';

const TrialScheduleContainer = () => {
  const [form] = Form.useForm();
  const [currentEvent, setCurrentEvent] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
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

    if (!targetTrialId) {
      logger.error('无法确定要更新的试验项目。');
      return;
    }

    try {
      // 统一使用 updateTrial 来处理试验及其时间段的更新（包括新增、修改、删除时间段）
      const updatePayload = {
        title: values.title,
        client: values.client,
        description: values.description,
        equipment_ids: values.equipment_ids || [],
        responsible_person_ids: values.responsible_person_ids || [],
        time_slots_data: values.time_slots_data, // 直接使用 CalendarEventModal 转换后的数据
      };
      await trialApi.updateTrial(targetTrialId, updatePayload);

      trialQueryClient.invalidateQueries(['trials']); // 刷新数据
      setCurrentEvent(null); // 关闭模态框
    } catch (error) {
      logger.error('保存试验失败:', error);
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
        time_ranges: trialDetails?.time_slots || eventObj.extendedProps?.time_ranges || [{
          start_time: eventObj.start,
          end_time: eventObj.end
        }],
      },
    };
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
        onDateClick={handleDateSelect}
        select={handleDateSelect}
        onEventClick={handleEventClick}
        slotMinTime="08:00:00"
        slotMaxTime="23:00:00"
      />

      {currentEvent && (
        <CalendarEventModal
          isVisible={!!currentEvent}
          form={form}
          currentEvent={currentEvent}
          passedTrials={trials}
          isEditing={isEditing}
          setIsEditing={setIsEditing}
          selectedTrial={selectedTrial}
          onSave={handleSaveTrial} // 将试验保存逻辑传递给 CalendarEventModal
          onCancel={() => setCurrentEvent(null)}
          onDelete={() => {
            trialQueryClient.invalidateQueries(['trials']);
          }}
          onSwap={() => {
            trialQueryClient.invalidateQueries(['trials']);
          }}
        />
      )}

    </>
  );
};

export default TrialScheduleContainer;