import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Calendar, dayjsLocalizer } from 'react-big-calendar';
import dayjs from 'dayjs';
import { Modal, Button, Form, Input, DatePicker, Select, message, Popconfirm, Tag, notification, Spin, Empty, Descriptions } from 'antd';
import { CalendarOutlined, UserOutlined, PhoneOutlined } from '@ant-design/icons';
import { useAuth } from '../../auth/context/AuthContext';
import {
    useMeetingRooms,
    useMeetingRoomBookings,
    useCreateMeetingRoomBooking,
    useUpdateMeetingRoomBooking,
    useDeleteMeetingRoomBooking,
} from '../hooks/useMeetingRoomData';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import './MeetingRoomBookingPage.css';

const localizer = dayjsLocalizer(dayjs);
const { RangePicker } = DatePicker;
const { Option } = Select;
const { TextArea } = Input;

const CustomToolbar = ({ label, onNavigate, onView, view }) => {
    const navigate = (action) => {
        onNavigate(action);
    };

    const viewNames = {
        month: '月',
        week: '周',
        day: '日',
        agenda: '议程',
    };

    const getNavText = (direction, currentView) => {
        switch (currentView) {
            case 'month':
                return direction === 'PREV' ? '上个月' : '下个月';
            case 'week':
                return direction === 'PREV' ? '上一周' : '下一周';
            case 'day':
                return direction === 'PREV' ? '上一天' : '下一天';
            case 'agenda':
                return direction === 'PREV' ? '上一页' : '下一页';
            default:
                return direction === 'PREV' ? '上一个' : '下一个';
        }
    };

    return (
        <div className="rbc-toolbar">
            <span className="rbc-btn-group">
                <button type="button" onClick={() => navigate('PREV')}>
                    {getNavText('PREV', view)}
                </button>
                <button type="button" onClick={() => navigate('TODAY')}>
                    今天
                </button>
                <button type="button" onClick={() => navigate('NEXT')}>
                    {getNavText('NEXT', view)}
                </button>
            </span>

            <span className="rbc-toolbar-label">{label}</span>

            <span className="rbc-btn-group">
                {Object.keys(viewNames).map((name) => (
                    <button
                        type="button"
                        key={name}
                        className={view === name ? 'rbc-active' : ''}
                        onClick={() => onView(name)}
                    >
                        {viewNames[name]}
                    </button>
                ))}
            </span>
        </div>
    );
};

CustomToolbar.propTypes = {
  label: PropTypes.string.isRequired,
  onNavigate: PropTypes.func.isRequired,
  onView: PropTypes.func.isRequired,
  view: PropTypes.string.isRequired,
};

const EventComponent = ({ event }) => {
    const eventRef = useRef(null);
    const [showDetails, setShowDetails] = useState(true);

    useEffect(() => {
        if (!eventRef.current) return;

        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                const minHeightForDetails = 35;
                setShowDetails(entry.contentRect.height > minHeightForDetails);
            }
        });

        observer.observe(eventRef.current);

        return () => {
            observer.disconnect();
        };
    }, []);

    return (
        <div
            ref={eventRef}
            style={{
                height: '100%',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                textAlign: 'center',
                fontSize: '0.8em',
                lineHeight: '1.2',
            }}
        >
            <div style={{ fontWeight: 'bold' }}>{event.title}</div>
            {showDetails && (
                <div style={{ fontSize: '0.9em', color: 'rgba(255, 255, 255, 0.85)' }}>
                    {event.meeting_room_name}
                </div>
            )}
        </div>
    );
};

EventComponent.propTypes = {
    event: PropTypes.object.isRequired,
};

const MeetingRoomLegend = ({ meetingRooms, roomColorMap }) => (
    <div className="meeting-room-legend">
        <h4>会议室颜色图例</h4>
        <div className="legend-items">
            {meetingRooms.map(room => (
                <div key={room.id} className="legend-item">
                    <span
                        className="legend-color-dot"
                        style={{ backgroundColor: roomColorMap.get(room.id) }}
                    />
                    <Tag color={roomColorMap.get(room.id)}>
                        {room.name}
                    </Tag>
                </div>
            ))}
        </div>
    </div>
);

MeetingRoomLegend.propTypes = {
    meetingRooms: PropTypes.array.isRequired,
    roomColorMap: PropTypes.instanceOf(Map).isRequired,
};

const MeetingRoomBookingPage = () => {
    const { user, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [form] = Form.useForm();
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);
    const [currentBooking, setCurrentBooking] = useState(null);
    const [selectedEvent, setSelectedEvent] = useState(null);
    const { data: meetingRooms = [], isLoading: isRoomsLoading } = useMeetingRooms();
    const { data: bookings = [], isLoading: isBookingsLoading } = useMeetingRoomBookings();
    const isLoading = isRoomsLoading || isBookingsLoading;
    const createBookingMutation = useCreateMeetingRoomBooking();
    const updateBookingMutation = useUpdateMeetingRoomBooking();
    const deleteBookingMutation = useDeleteMeetingRoomBooking();

    const minTime = new Date();
    minTime.setHours(8, 0, 0);
    const maxTime = new Date();
    maxTime.setHours(22, 0, 0);

    const roomColors = useMemo(() => [
        '#f87171', '#2dd4bf', '#38bdf8', '#fbbf24', '#22d3ee',
        '#fb923c', '#f472b6', '#93c5fd', '#c084fc', '#f9a8d4',
        '#fde68a', '#7dd3fc', '#fdba74', '#fca5a5', '#8b5cf6'
    ], []);

    const roomColorMap = useMemo(() => {
        const map = new Map();
        meetingRooms.forEach((room, index) => {
            map.set(room.id, roomColors[index % roomColors.length]);
        });
        return map;
    }, [meetingRooms, roomColors]);

    const isAdminOrManager = useMemo(() => {
        return isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');
    }, [isAuthenticated, user]);

    const handleSelectSlot = ({ start, end }) => {
        if (!user.real_name || !user.phone_numbers || user.phone_numbers.length === 0) {
            notification.error({
                message: '信息不完整',
                description: (
                    <div>
                        请先完善您的真实姓名和联系电话。
                        <Button type="link" onClick={() => navigate('/profile')}>
                            去完善
                        </Button>
                    </div>
                ),
            });
            return;
        }
        // 预约时间不能在当前时间之前
        if (dayjs(start).isBefore(dayjs())) {
            message.warning('无法预约过去的时间段。');
            return;
        }
        setCurrentBooking(null); // Clear any previous selection
        form.resetFields();
        form.setFieldsValue({
            timeRange: [dayjs(start), dayjs(end)],
            meeting_room: meetingRooms.length > 0 ? meetingRooms[0].id : undefined // 默认选择第一个会议室
        });
        setIsModalVisible(true);
    };

    const handleSelectEvent = (event) => {
        setSelectedEvent(event);
        setIsDetailModalVisible(true);
    };

    const handleEditEvent = () => {
        if (!selectedEvent) return;

        // Check for permission before opening edit modal
        if (!isAdminOrManager && selectedEvent.user.id !== user.id) {
            message.warning('您没有权限编辑此预约。');
            return;
        }

        setIsDetailModalVisible(false); // Close detail modal
        setCurrentBooking(selectedEvent);
        form.setFieldsValue({
            meeting_room: selectedEvent.meeting_room,
            timeRange: [dayjs(selectedEvent.start), dayjs(selectedEvent.end)],
            title: selectedEvent.title,
            participants: selectedEvent.participants,
            description: selectedEvent.description,
        });
        setIsModalVisible(true);
    };

    const handleOk = async () => {
        if (!user.real_name || !user.phone_numbers || user.phone_numbers.length === 0) {
            notification.error({
                message: '信息不完整',
                description: (
                    <div>
                        请先完善您的真实姓名和联系电话。
                        <Button type="link" onClick={() => navigate('/profile')}>
                            去完善
                        </Button>
                    </div>
                ),
            });
            return;
        }
        try {
            const values = await form.validateFields();
            const [start_time, end_time] = values.timeRange;

            const bookingData = {
                meeting_room: values.meeting_room,
                start_time: start_time.toISOString(),
                end_time: end_time.toISOString(),
                title: values.title,
                participants: values.participants,
                description: values.description,
            };

            if (currentBooking) {
                await updateBookingMutation.mutateAsync({ id: currentBooking.id, data: bookingData });
            } else {
                await createBookingMutation.mutateAsync(bookingData);
            }
            setIsModalVisible(false);
        } catch (error) {
            message.error('操作失败，请重试');
        }
    };

    const handleDelete = async (bookingId) => {
        await deleteBookingMutation.mutateAsync(bookingId);
        setIsModalVisible(false);
    };

    const eventPropGetter = useCallback((event) => {
        const backgroundColor = roomColorMap.get(event.meeting_room) || '#6c757d';
        const style = {
            backgroundColor: backgroundColor,
            borderRadius: '6px',
            opacity: 0.9,
            color: 'white',
            border: 'none',
            display: 'block',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)',
        };
        return {
            style: style,
            'data-testid': `booking-event-${event.id}`,
        };
    }, [roomColorMap]);

    return (
        <div className="calendar-page-container">
            <div className="calendar-page-header">
                <h1>会议室预约</h1>
            </div>
            <Spin spinning={isLoading} tip="正在加载会议室数据...">
                <div className="calendar-page-content">
                    {bookings.length === 0 && !isLoading && (
                        <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
                            <Empty description="暂无会议室预约" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                        </div>
                    )}
                    <div className="calendar-wrapper">
                    <Calendar
                        localizer={localizer}
                    events={bookings}
                    startAccessor="start"
                    endAccessor="end"
                    selectable
                    onSelectSlot={handleSelectSlot}
                    onSelectEvent={handleSelectEvent}
                    views={['month', 'week', 'day', 'agenda']}
                    defaultView="week"
                    min={minTime}
                    max={maxTime}
                    components={{
                        toolbar: CustomToolbar,
                        event: EventComponent,
                    }}
                    eventPropGetter={eventPropGetter}
                    dayLayoutAlgorithm="no-overlap"
                    culture="zh-CN"
                    formats={{
                        timeGutterFormat: 'HH:mm',
                        eventTimeRangeFormat: () => '',
                        dayFormat: 'M/D (ddd)',
                        monthHeaderFormat: 'YYYY年M月',
                        weekHeaderFormat: (date) => `${dayjs(date.start).format('YYYY年M月D日')} - ${dayjs(date.end).format('YYYY年M月D日')}`,
                        dayHeaderFormat: 'YYYY年M月D日 (ddd)',
                        agendaDateFormat: 'M/D (ddd)',
                        agendaTimeFormat: 'HH:mm',
                        agendaTimeRangeFormat: () => '',
                    }}
                    />
                </div>
                <div className="calendar-sidebar">
                    <MeetingRoomLegend meetingRooms={meetingRooms} roomColorMap={roomColorMap} />
                </div>
            </div>

            <Modal
                title={currentBooking ? "编辑会议室预约" : "新建会议室预约"}
                open={isModalVisible}
                onOk={handleOk}
                onCancel={() => setIsModalVisible(false)}
                footer={[
                    <Button key="back" onClick={() => setIsModalVisible(false)}>
                        取消
                    </Button>,
                    currentBooking && (isAdminOrManager || currentBooking.user.id === user.id) && (
                        <Popconfirm
                            key="delete-popconfirm"
                            title="确定删除此预约吗？"
                            onConfirm={() => handleDelete(currentBooking.id)}
                            okText="是"
                            cancelText="否"
                        >
                            <Button key="delete" danger>
                                删除
                            </Button>
                        </Popconfirm>
                    ),
                    <Button key="submit" type="primary" loading={createBookingMutation.isPending || updateBookingMutation.isPending} onClick={handleOk}>
                        {currentBooking ? "更新" : "创建"}
                    </Button>,
                ]}
            >
                <Form form={form} layout="vertical">
                    <Form.Item
                        name="meeting_room"
                        label="会议室"
                        rules={[{ required: true, message: '请选择会议室!' }]}
                    >
                        <Select placeholder="选择会议室">
                            {meetingRooms.map(room => (
                                <Option key={room.id} value={room.id}>{room.name}</Option>
                            ))}
                        </Select>
                    </Form.Item>
                    <Form.Item
                        name="timeRange"
                        label="时间范围"
                        rules={[{ required: true, message: '请选择时间范围!' }]}
                    >
                        <RangePicker
                            showTime={{ format: 'HH:mm' }}
                            format="YYYY-MM-DD HH:mm"
                            style={{ width: '100%' }}
                        />
                    </Form.Item>
                    <Form.Item
                        name="title"
                        label="主题"
                        rules={[{ required: true, message: '请输入预约主题!' }]}
                    >
                        <Input />
                    </Form.Item>
                    <Form.Item
                        name="participants"
                        label="参与人员 (可选)"
                    >
                        <Input />
                    </Form.Item>
                    <Form.Item
                        name="description"
                        label="描述 (可选)"
                    >
                        <TextArea rows={3} />
                    </Form.Item>
                </Form>
            </Modal>

            <Modal
                title="预约详情"
                open={isDetailModalVisible}
                onCancel={() => setIsDetailModalVisible(false)}
                footer={[
                    <Button key="back" onClick={() => setIsDetailModalVisible(false)}>
                        关闭
                    </Button>,
                    selectedEvent && (isAdminOrManager || selectedEvent.user.id === user.id) && (
                        <Button key="edit" type="primary" onClick={handleEditEvent}>
                            编辑
                        </Button>
                    )
                ]}
            >
                {selectedEvent && (
                    <Descriptions bordered column={1} size="small">
                        <Descriptions.Item label="主题">{selectedEvent.title}</Descriptions.Item>
                        <Descriptions.Item label="会议室">{selectedEvent.meeting_room_name}</Descriptions.Item>
                        <Descriptions.Item label="时间">{`${dayjs(selectedEvent.start).format('YYYY-MM-DD HH:mm')} - ${dayjs(selectedEvent.end).format('HH:mm')}`}</Descriptions.Item>
                        <Descriptions.Item label={<><UserOutlined /> 发布人</>}>{selectedEvent.user.real_name || selectedEvent.user.username}</Descriptions.Item>
                        <Descriptions.Item label={<><PhoneOutlined /> 联系电话</>}>{selectedEvent.user.phone_numbers?.[0]?.number || '未提供'}</Descriptions.Item>
                        <Descriptions.Item label="参与人员">{selectedEvent.participants || '无'}</Descriptions.Item>
                        <Descriptions.Item label={<><CalendarOutlined /> 描述</>}>{selectedEvent.description || '无'}</Descriptions.Item>
                    </Descriptions>
                )}
            </Modal>
            </Spin>
        </div>
    );
};

export default MeetingRoomBookingPage;