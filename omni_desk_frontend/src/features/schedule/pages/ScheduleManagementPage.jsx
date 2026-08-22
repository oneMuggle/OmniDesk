import { useState, useEffect, useRef, useMemo } from 'react';
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query';
import { Card, Table, Button, message, Space, Radio, Switch } from 'antd';
// R5-C2: jspdf/html2canvas 仅"导出为PDF"时使用,改为动态 import 拆 chunk,
// 避免进入首屏依赖图(docprocessing chunk 约 620 kB raw / 188 kB gzip)。
import { scheduleApi } from '../api/scheduleApi';
import { getPositions, getAllPersonnel } from '../../personnel/api/personnelApi';
import { getPersonnelSequences, getLeaderSequences } from '../../../shared/api/sequenceApi';
import '../../../shared/components/styles/Schedule.css';
import dayjs from 'dayjs';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import PersonnelSequenceModal from '../../../shared/components/Schedule/PersonnelSequenceModal';
import WeeklyLeaderDisplay from '../../../shared/components/Schedule/WeeklyLeaderDisplay';
import MonthlyLeaderSidebar from '../../../shared/components/Schedule/MonthlyLeaderSidebar';
import { DragDropContext } from '@hello-pangea/dnd';
import { logger } from '../../../shared/utils/logger';
import { computeWeeklyLeaders } from '../utils/computeWeeklyLeaders';
import ScheduleFormModal from '../components/ScheduleFormModal';
import GenerateScheduleModal from '../components/GenerateScheduleModal';
import { createScheduleColumns } from '../utils/scheduleColumns.jsx';

const ScheduleManagementPage = () => {
  const queryClient = useQueryClient();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isPersonnelSequenceModalVisible, setIsPersonnelSequenceModalVisible] = useState(false);
  const [currentSequence, setCurrentSequence] = useState(null);
  const [formInitialValues, setFormInitialValues] = useState({});
  const [isExporting, setIsExporting] = useState(false);
  const calendarRef = useRef(null);
  const calendarContainerRef = useRef(null);
  const originalCalendarContainerStyle = useRef({});
  const [selectedSchedules, setSelectedSchedules] = useState([]);
  const [isAllSelected, setIsAllSelected] = useState(false);
  const [isCalendarFilterEnabled, setIsCalendarFilterEnabled] = useState(false);
  const [calendarViewInfo, setCalendarViewInfo] = useState(null);
  const [currentView, setCurrentView] = useState('dayGridMonth');
  const [viewMode, setViewMode] = useState('calendar');
  const [weeklyLeaders, setWeeklyLeaders] = useState([]);

  const schedulesQuery = useQuery({
    queryKey: ['schedules'],
    queryFn: scheduleApi.fetchSchedules,
  });


  // R4-B4: 手动 while 翻页拉全量 personnel → 复用 getAllPersonnel(personnelApi.js)
  const personnelQuery = useQuery({
    queryKey: ['personnel'],
    queryFn: () => getAllPersonnel().then(res => res.data.results),
  });

  const positionsQuery = useQuery({
    queryKey: ['positions'],
    queryFn: () => getPositions().then(res => res.data.results),
  });

  const personnelSequencesQuery = useQuery({
    queryKey: ['personnelSequences'],
    queryFn: () => getPersonnelSequences().then(res => res.data.results),
  });

  const leaderSequencesQuery = useQuery({
    queryKey: ['leaderSequences'],
    queryFn: () => getLeaderSequences().then(res => res.data.results),
  });

  const schedules = useMemo(() => schedulesQuery.data || [], [schedulesQuery.data]);
  const personnel = personnelQuery.data || [];
  const positions = positionsQuery.data || [];
  const personnelSequences = personnelSequencesQuery.data || [];
  const leaderSequences = leaderSequencesQuery.data || [];

  const isDataPending =
    schedulesQuery.isPending ||
    personnelQuery.isPending ||
    positionsQuery.isPending ||
    personnelSequencesQuery.isPending ||
    leaderSequencesQuery.isPending;

  const invalidateSchedules = () => {
    queryClient.invalidateQueries({ queryKey: ['schedules'] });
  };

  const createOrUpdateMutation = useMutation({
    mutationFn: (values) =>
      formInitialValues.id
        ? scheduleApi.updateSchedule(formInitialValues.id, values)
        : scheduleApi.createSchedule(values),
    onSuccess: () => {
      message.success(formInitialValues.id ? '排班更新成功' : '排班创建成功');
      invalidateSchedules();
      setIsModalVisible(false);
    },
    onError: () => {
      message.error('保存排班失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => scheduleApi.deleteSchedule(id),
    onSuccess: () => {
      message.success('排班删除成功');
      invalidateSchedules();
    },
    onError: () => {
      message.error('删除排班失败');
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids) => scheduleApi.bulkDeleteSchedules(ids),
    onSuccess: () => {
      message.success('批量删除成功');
      invalidateSchedules();
      setSelectedSchedules([]);
    },
    onError: () => {
      message.error('批量删除失败');
    },
  });

  const generateMutation = useMutation({
    mutationFn: (values) => scheduleApi.generateSchedules(values),
    onSuccess: () => {
      message.success('排班生成成功');
      invalidateSchedules();
      setIsGenerateModalVisible(false);
    },
    onError: (error) => {
      const errorMsg = error.response?.data?.error || '生成排班失败';
      message.error(errorMsg);
    },
  });

  const swapDatesMutation = useMutation({
    mutationFn: ({ draggedId, targetId }) => scheduleApi.swapScheduleDates(draggedId, targetId),
    onSuccess: () => {
      message.success('排班交换成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新排班失败');
      context?.revert?.();
    },
  });

  const updateDateMutation = useMutation({
    mutationFn: ({ id, data }) => scheduleApi.updateSchedule(id, data),
    onSuccess: () => {
      message.success('排班日期更新成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新排班失败');
      context?.revert?.();
    },
  });

  const swapLeadersMutation = useMutation({
    mutationFn: (data) => scheduleApi.swapWeeklyLeaders(data),
    onSuccess: () => {
      message.success('值班领导顺序更新成功');
      invalidateSchedules();
    },
    onError: (_error, _variables, context) => {
      message.error('更新值班领导顺序失败');
      setWeeklyLeaders(context?.previousWeeklyLeaders ?? weeklyLeaders);
    },
  });

  useEffect(() => {
    if (calendarContainerRef.current) {
      originalCalendarContainerStyle.current = {
        width: calendarContainerRef.current.style.width,
        height: calendarContainerRef.current.style.height,
      };
    }
  }, []);

  const handleAdd = () => {
    setFormInitialValues({ id: null });
    setIsModalVisible(true);
  };

  const handleEdit = (record) => {
    const initialValues = {
      id: record.id,
      date: record.duty_date ? dayjs(record.duty_date) : null,
      duty_person: record.duty_person?.id,
      duty_leader: record.duty_leader?.id,
      person_position_filter: record.duty_person?.position?.id,
      leader_position_filter: record.duty_leader?.position?.id,
      duty_person_phone: record.duty_person?.phone_number || '',
      duty_leader_phone: record.duty_leader?.phone_number || '',
    };
    setFormInitialValues(initialValues);
    setIsModalVisible(true);
  };

  const handleDelete = (id) => {
    deleteMutation.mutate(id);
  };

  const handleBulkDelete = () => {
    if (selectedSchedules.length === 0) {
      message.info('请先选择要删除的排班');
      return;
    }
    bulkDeleteMutation.mutate(selectedSchedules);
  };

  const handleModalOk = (values) => {
    createOrUpdateMutation.mutate(values);
  };

  const handlePersonnelSequenceModalOk = () => {
    setIsPersonnelSequenceModalVisible(false);
    setCurrentSequence(null);
    queryClient.invalidateQueries({ queryKey: ['personnelSequences', 'leaderSequences'] });
    message.success('人员顺序已成功保存');
  };

  const handlePersonnelSequenceModalCancel = () => {
    setIsPersonnelSequenceModalVisible(false);
    setCurrentSequence(null);
  };

  const handleGenerateModalOk = (values) => {
    generateMutation.mutate(values);
  };

  const handleEventDrop = (info) => {
    const { event: draggedEvent, revert } = info;
    const newDate = dayjs(draggedEvent.start).format('YYYY-MM-DD');
    const targetEvent = schedules.find(s =>
      dayjs(s.duty_date).format('YYYY-MM-DD') === newDate && String(s.id) !== draggedEvent.id
    );
    const draggedId = parseInt(draggedEvent.id, 10);

    if (targetEvent) {
      const targetId = parseInt(targetEvent.id, 10);
      swapDatesMutation.mutate({ draggedId, targetId }, { context: { revert } });
    } else {
      const scheduleData = {
        date: newDate,
        duty_person_id: draggedEvent.extendedProps.duty_person.id,
        duty_leader_id: draggedEvent.extendedProps.duty_leader.id,
      };
      updateDateMutation.mutate({ id: draggedId, data: scheduleData }, { context: { revert } });
    }
  };

  const handleEventClick = (info) => {
    const scheduleId = parseInt(info.event.id, 10);
    const clickedSchedule = schedules.find(s => s.id === scheduleId);
    if (clickedSchedule) {
      handleEdit(clickedSchedule);
    } else {
      message.error('未找到对应的排班数据');
    }
  };

  useEffect(() => {
    const leaders = computeWeeklyLeaders(schedules, calendarViewInfo);
    setWeeklyLeaders(leaders);
  }, [schedules, calendarViewInfo]);

  const handleDatesSet = (viewInfo) => {
    setCalendarViewInfo(viewInfo);
    setCurrentView(viewInfo.view.type);
  };

  const handleLeaderDragEnd = async (result) => {
    if (!result.destination) return;

    const previousWeeklyLeaders = weeklyLeaders;
    const newWeeklyLeaders = Array.from(weeklyLeaders);
    const [reorderedItem] = newWeeklyLeaders.splice(result.source.index, 1);
    newWeeklyLeaders.splice(result.destination.index, 0, reorderedItem);
    setWeeklyLeaders(newWeeklyLeaders);

    const sourceWeek = weeklyLeaders[result.source.index];
    const destinationWeek = weeklyLeaders[result.destination.index];

    swapLeadersMutation.mutate({
      source_week_start_date: sourceWeek.start,
      destination_week_start_date: destinationWeek.start,
    }, { context: { previousWeeklyLeaders } });
  };

  const calendarEvents = useMemo(() => {
    return schedules.map(schedule => {
      const dutyPerson = schedule.duty_person;
      const dutyLeader = schedule.duty_leader;
      return {
        id: String(schedule.id),
        start: schedule.duty_date,
        allDay: true,
        extendedProps: {
          duty_person: {
            ...dutyPerson,
            name: dutyPerson?.username || dutyPerson?.name,
          },
          duty_leader: {
            ...dutyLeader,
            name: dutyLeader?.username || dutyLeader?.name,
          },
        }
      };
    });
  }, [schedules]);

  const renderEventContent = (eventInfo) => {
    const { duty_person, duty_leader } = eventInfo.event.extendedProps;
    return (
      <div className="calendar-event-card">
        <div className="event-card-row">
          <span className="event-card-name">{duty_person?.name || ''}</span>
        </div>
        <div className="event-card-row event-card-muted">
          <span>{duty_leader?.name || ''}</span>
        </div>
      </div>
    );
  };

  const filteredSchedules = useMemo(() => {
    if (!isCalendarFilterEnabled || !calendarViewInfo) {
      return schedules;
    }
    const viewStart = dayjs(calendarViewInfo.start).startOf('day');
    const viewEnd = dayjs(calendarViewInfo.end).endOf('day');
    return schedules.filter(schedule => {
      const dutyDate = dayjs(schedule.duty_date);
      return dutyDate.isBetween(viewStart, viewEnd, null, '[]');
    });
  }, [schedules, isCalendarFilterEnabled, calendarViewInfo]);

  const handleSelectAll = () => {
    if (isAllSelected) {
      setSelectedSchedules([]);
    } else {
      setSelectedSchedules(filteredSchedules.map(s => s.id));
    }
    setIsAllSelected(!isAllSelected);
  };

  const handleInvertSelection = () => {
    const allIds = filteredSchedules.map(s => s.id);
    const newSelectedIds = allIds.filter(id => !selectedSchedules.includes(id));
    setSelectedSchedules(newSelectedIds);
    setIsAllSelected(newSelectedIds.length === allIds.length && allIds.length > 0);
  };

  const rowSelection = {
    selectedRowKeys: selectedSchedules,
    onChange: (keys) => {
      setSelectedSchedules(keys);
      setIsAllSelected(keys.length === filteredSchedules.length && filteredSchedules.length > 0);
    },
  };

  const exportToPDF = async () => {
    setIsExporting(true);
    await new Promise(resolve => setTimeout(resolve, 500));
    const calendarEl = calendarContainerRef.current;
    if (!calendarEl) {
      message.error('无法找到日历元素');
      setIsExporting(false);
      return;
    }
    const originalWidth = calendarEl.style.width;
    const originalHeight = calendarEl.style.height;
    calendarEl.style.width = 'auto';
    calendarEl.style.height = 'auto';
    try {
      const [{ default: html2canvas }, { default: JsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ]);
      const canvas = await html2canvas(calendarEl, { scale: 2, useCORS: true });
      const pdf = new JsPDF({ orientation: 'landscape', unit: 'px', format: [canvas.width, canvas.height] });
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, canvas.width, canvas.height);
      pdf.save('schedule.pdf');
    } catch (error) {
      logger.error("导出PDF时出错:", error);
      message.error('导出PDF失败');
    } finally {
      calendarEl.style.width = originalWidth;
      calendarEl.style.height = originalHeight;
      setIsExporting(false);
    }
  };

  // R4-B4: columns 提升到 utils/scheduleColumns.js 的 createScheduleColumns
  const columns = createScheduleColumns(handleEdit, handleDelete);

  return (
    <div className="p-4" data-testid="schedule-management-page">
      <h1 className="text-2xl font-bold mb-4">排班管理</h1>
      <Card loading={isDataPending}>
        <div className="flex justify-between items-center mb-4">
          <Space>
            <Button type="primary" onClick={handleAdd} data-testid="add-schedule-button">新增排班</Button>
            <Button type="default" onClick={() => setIsGenerateModalVisible(true)} data-testid="generate-schedule-button">生成排班</Button>
            <Button type="default" onClick={() => setIsPersonnelSequenceModalVisible(true)} data-testid="manage-personnel-sequence-button">管理人员顺序</Button>
          </Space>
          <Space>
           <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
             <Radio.Button value="calendar">日历</Radio.Button>
             <Radio.Button value="list">列表</Radio.Button>
           </Radio.Group>
            <Switch
              checkedChildren="日历筛选已开启"
              unCheckedChildren="日历筛选已关闭"
              checked={isCalendarFilterEnabled}
              onChange={setIsCalendarFilterEnabled}
              data-testid="calendar-filter-switch"
            />
            <Button onClick={exportToPDF} loading={isExporting} data-testid="export-pdf-button">导出为PDF</Button>
          </Space>
        </div>

       {viewMode === 'calendar' && (
         <DragDropContext onDragEnd={handleLeaderDragEnd}>
           <div style={{ display: 'flex' }}>
             <div ref={calendarContainerRef} style={{ flex: 1 }}>
               {currentView === 'dayGridWeek' && <WeeklyLeaderDisplay leaders={weeklyLeaders.length > 0 ? weeklyLeaders[0].leaders : []} />}
               <FullCalendar
                 data-testid="full-calendar"
                 ref={calendarRef}
                 plugins={[dayGridPlugin, interactionPlugin]}
                 initialView="dayGridMonth"
                 headerToolbar={{
                   left: 'prev,next today',
                   center: 'title',
                   right: 'dayGridMonth,dayGridWeek'
                 }}
                 events={calendarEvents}
                 editable={true}
                 droppable={true}
                 eventDrop={handleEventDrop}
                 eventClick={handleEventClick}
                 eventContent={renderEventContent}
                 datesSet={handleDatesSet}
                 locale="zh-cn"
                 firstDay={1}
                 slotMinTime="08:00:00"
                 slotMaxTime="23:00:00"
               />
             </div>
             {currentView === 'dayGridMonth' && (
               <MonthlyLeaderSidebar
                 weeklyLeaders={weeklyLeaders}
                 calendarRef={calendarRef}
                 isDragDisabled={swapLeadersMutation.isPending}
               />
             )}
           </div>
         </DragDropContext>
       )}

       {viewMode === 'list' && (
         <div className="mt-4">
           <Space className="mb-2">
             <Button onClick={handleSelectAll} data-testid="select-all-button">全选</Button>
             <Button onClick={handleInvertSelection} data-testid="invert-selection-button">反选</Button>
             <Button danger onClick={handleBulkDelete} disabled={selectedSchedules.length === 0 || bulkDeleteMutation.isPending} data-testid="bulk-delete-button">批量删除</Button>
           </Space>
           <Table
             columns={columns}
             dataSource={filteredSchedules}
             rowKey="id"
             loading={isDataPending}
             rowSelection={rowSelection}
             pagination={{ pageSize: 10 }}
             data-testid="schedule-table"
           />
         </div>
       )}
      </Card>
      {isModalVisible && (
        <ScheduleFormModal
          key={formInitialValues.id || 'new-schedule'}
          open={isModalVisible}
          onCancel={() => {
            setIsModalVisible(false);
            setFormInitialValues({});
          }}
          onOk={handleModalOk}
          initialValues={formInitialValues}
          personnelList={personnel}
          positions={positions}
        />
      )}
      {isGenerateModalVisible && (
        <GenerateScheduleModal
          open={isGenerateModalVisible}
          onCancel={() => setIsGenerateModalVisible(false)}
          onOk={handleGenerateModalOk}
          personnelSequences={personnelSequences}
          leaderSequences={leaderSequences}
        />
      )}
      {isPersonnelSequenceModalVisible && (
        <PersonnelSequenceModal
          open={isPersonnelSequenceModalVisible}
          onOk={handlePersonnelSequenceModalOk}
          onCancel={handlePersonnelSequenceModalCancel}
          personnelList={personnel}
          sequence={currentSequence}
          positions={positions}
        />
      )}
    </div>
  );
};

export default ScheduleManagementPage;
