import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Calendar, dayjsLocalizer } from 'react-big-calendar';
import dayjs from 'dayjs';
import { Modal, Button, Form, Input, DatePicker, Select, message, Popconfirm, Tag, notification } from 'antd';
import { useAuth } from '../context/AuthContext';
import meetingRoomApi from '../api/meetingRoomApi';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import '../components/CalendarPage.css'; // 假设你有一个通用的日历样式文件

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

const MeetingRoomBookingPage = () => {
    const { user, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [form] = Form.useForm();
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);
    const [currentBooking, setCurrentBooking] = useState(null);
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [meetingRooms, setMeetingRooms] = useState([]);
    const [bookings, setBookings] = useState([]);
    const [loading, setLoading] = useState(false);

    const roomColors = useMemo(() => [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FED766', '#2AB7CA',
        '#F0B7A4', '#F18C8E', '#A8D8EA', '#AA96DA', '#FCBAD3',
        '#FFFFD2', '#A2D5F2', '#FFC3A0', '#D4A5A5', '#392F5A'
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

    const fetchMeetingRooms = useCallback(async () => {
        try {
            const response = await meetingRoomApi.getMeetingRooms();
            setMeetingRooms(response.data.results || []);
        } catch (error) {
            message.error('获取会议室列表失败。');
            console.error('Failed to fetch meeting rooms:', error.response || error);
        }
    }, []);

    const fetchBookings = useCallback(async () => {
        setLoading(true);
        try {
            const response = await meetingRoomApi.getMeetingRoomBookings();
            const bookingsData = response.data.results || [];
            setBookings(bookingsData.map(booking => ({
                ...booking,
                start: new Date(booking.start_time),
                end: new Date(booking.end_time),
            })));
        } catch (error) {
            message.error('获取预约信息失败。');
            console.error('Failed to fetch bookings:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchMeetingRooms();
        fetchBookings();
    }, [fetchMeetingRooms, fetchBookings]);


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
                await meetingRoomApi.updateMeetingRoomBooking(currentBooking.id, bookingData);
                message.success('预约更新成功！');
            } else {
                await meetingRoomApi.createMeetingRoomBooking(bookingData);
                message.success('预约创建成功！');
            }
            setIsModalVisible(false);
            fetchBookings(); // Refresh bookings
        } catch (error) {
            const errorMsg = error.response?.data?.detail || error.response?.data?.non_field_errors?.[0] || '操作失败，请重试。';
            message.error(errorMsg);
            console.error('Failed to save booking:', error);
        }
    };

    const handleDelete = async (bookingId) => {
        try {
            await meetingRoomApi.deleteMeetingRoomBooking(bookingId);
            message.success('预约删除成功！');
            setIsModalVisible(false);
            fetchBookings(); // Refresh bookings
        } catch (error) {
            message.error('删除预约失败。');
            console.error('Failed to delete booking:', error);
        }
    };

    const eventPropGetter = useCallback((event) => {
        const backgroundColor = roomColorMap.get(event.meeting_room) || '#6c757d';
        const style = {
            backgroundColor: backgroundColor,
            borderRadius: '0px',
            opacity: 0.8,
            color: 'white',
            border: '0px',
            display: 'block'
        };
        return {
            style: style,
            'data-testid': `booking-event-${event.id}`,
        };
    }, [roomColorMap]);

    const EventComponent = ({ event }) => {
        const eventRef = useRef(null);
        const [showDetails, setShowDetails] = useState(true);

        useEffect(() => {
            if (!eventRef.current) return;

            const observer = new ResizeObserver(entries => {
                // Use a loop in case there are multiple observations, though we expect one.
                for (const entry of entries) {
                    const minHeightForDetails = 35; // Height threshold in pixels
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

    const MeetingRoomLegend = () => (
        <div style={{ marginTop: '20px', padding: '10px', border: '1px solid #e8e8e8', borderRadius: '4px' }}>
            <h4>会议室颜色图例</h4>
            {meetingRooms.map(room => (
                <div key={room.id} style={{ display: 'flex', alignItems: 'center', marginBottom: '5px' }}>
                    <Tag color={roomColorMap.get(room.id)} style={{ marginRight: '8px' }}>
                        {room.name}
                    </Tag>
                </div>
            ))}
        </div>
    );

    return (
        <div className="calendar-page-container">
            <h1>会议室预约</h1>
            <div style={{ display: 'flex', gap: '20px' }}>
                <div style={{ flex: 1, height: 700 }}>
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
                    slotMinTime="08:00:00"
                    slotMaxTime="23:00:00"
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
                <div style={{ flex: '0 0 200px' }}>
                    <MeetingRoomLegend />
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
                    <Button key="submit" type="primary" loading={loading} onClick={handleOk}>
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
                    <div>
                        <p><strong>主题:</strong> {selectedEvent.title}</p>
                        <p><strong>会议室:</strong> {selectedEvent.meeting_room_name}</p>
                        <p><strong>时间:</strong> {`${dayjs(selectedEvent.start).format('YYYY-MM-DD HH:mm')} - ${dayjs(selectedEvent.end).format('HH:mm')}`}</p>
                        <p><strong>发布人:</strong> {selectedEvent.user.real_name || selectedEvent.user.username}</p>
                        <p><strong>联系电话:</strong> {selectedEvent.user.phone_numbers?.[0]?.number || '未提供'}</p>
                        <p><strong>参与人员:</strong> {selectedEvent.participants || '无'}</p>
                        <p><strong>描述:</strong> {selectedEvent.description || '无'}</p>
                    </div>
                )}
            </Modal>
        </div>
    );
};

export default MeetingRoomBookingPage;