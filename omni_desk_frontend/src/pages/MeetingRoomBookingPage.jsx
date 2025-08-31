import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Calendar, dayjsLocalizer } from 'react-big-calendar';
import dayjs from 'dayjs';
import { Modal, Button, Form, Input, DatePicker, Select, message, Popconfirm } from 'antd';
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

const MeetingRoomBookingPage = () => {
    const { user, isAuthenticated } = useAuth();
    const [form] = Form.useForm();
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [selectedSlot, setSelectedSlot] = useState(null); // Keep selectedSlot for handleSelectSlot
    const [currentBooking, setCurrentBooking] = useState(null);
    const [meetingRooms, setMeetingRooms] = useState([]);
    const [bookings, setBookings] = useState([]);
    const [loading, setLoading] = useState(false);

    const isAdminOrManager = useMemo(() => {
        return isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');
    }, [isAuthenticated, user]);

    const fetchMeetingRooms = useCallback(async () => {
        try {
            const response = await meetingRoomApi.getMeetingRooms();
            console.log('Meeting Rooms API Response:', response);
            console.log('Meeting Rooms Data:', response.data);
            setMeetingRooms(response.data.results);
        } catch (error) {
            message.error('获取会议室列表失败。');
            console.error('Failed to fetch meeting rooms:', error.response || error);
        }
    }, []);

    const fetchBookings = useCallback(async () => {
        setLoading(true);
        try {
            const response = await meetingRoomApi.getMeetingRoomBookings();
            setBookings(response.data.results.map(booking => ({
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
        // 预约时间不能在当前时间之前
        if (dayjs(start).isBefore(dayjs())) {
            message.warning('无法预约过去的时间段。');
            return;
        }
        setSelectedSlot({ start, end });
        setCurrentBooking(null); // Clear any previous selection
        form.resetFields();
        form.setFieldsValue({
            timeRange: [dayjs(start), dayjs(end)],
            meeting_room: meetingRooms.length > 0 ? meetingRooms[0].id : undefined // 默认选择第一个会议室
        });
        setIsModalVisible(true);
    };

    const handleSelectEvent = (event) => {
        // 普通用户只能编辑自己的预约
        if (!isAdminOrManager && event.user.id !== user.id) {
            message.info('您没有权限编辑此预约。');
            return;
        }

        setCurrentBooking(event);
        setSelectedSlot(null); // Clear selected slot
        form.setFieldsValue({
            meeting_room: event.meeting_room,
            timeRange: [dayjs(event.start), dayjs(event.end)],
            title: event.title,
            participants: event.participants,
            description: event.description,
        });
        setIsModalVisible(true);
    };

    const handleOk = async () => {
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

    const eventPropGetter = useCallback((event, start, end, isSelected) => {
        const style = {
            backgroundColor: event.user.id === user?.id ? '#3174ad' : '#6c757d', // 自己的预约蓝色，别人的灰色
            borderRadius: '0px',
            opacity: 0.8,
            color: 'white',
            border: '0px',
            display: 'block'
        };
        return {
            style: style
        };
    }, [user]);

    const getEventTitle = useCallback((event) => {
        const duration = dayjs(event.end).diff(dayjs(event.start), 'minute'); // 计算持续时间（分钟）

        if (duration < 60) { // 如果持续时间小于60分钟，只显示主题和时间
            return (
                <div style={{ padding: '2px', fontSize: '0.8em' }}>
                    <div><strong>{event.title}</strong></div>
                    <div>{dayjs(event.start).format('HH:mm')} - {dayjs(event.end).format('HH:mm')}</div>
                </div>
            );
        } else {
            return (
                <div style={{ padding: '5px' }}>
                    <div style={{ marginBottom: '3px' }}><strong>主题:</strong> {event.title}</div>
                    <div style={{ marginBottom: '3px' }}><strong>会议室:</strong> {event.meeting_room_name}</div>
                    <div style={{ marginBottom: '3px' }}><strong>时间:</strong> {dayjs(event.start).format('HH:mm')} - {dayjs(event.end).format('HH:mm')}</div>
                    <div><strong>发布人:</strong> {event.user.username}</div>
                </div>
            );
        }
    }, []);

    return (
        <div className="calendar-page-container">
            <h1>会议室预约</h1>
            <div style={{ height: 700 }}>
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
                    components={{
                        toolbar: CustomToolbar,
                    }}
                    eventPropGetter={eventPropGetter}
                    titleAccessor={getEventTitle}
                    culture="zh-CN"
                    formats={{
                        timeGutterFormat: 'HH:mm',
                        eventTimeRangeFormat: ({ start, end }) => `${dayjs(start).format('HH:mm')} - ${dayjs(end).format('HH:mm')}`,
                        dayFormat: 'M/D (ddd)',
                        monthHeaderFormat: 'YYYY年M月',
                        weekHeaderFormat: (date) => `${dayjs(date.start).format('YYYY年M月D日')} - ${dayjs(date.end).format('YYYY年M月D日')}`,
                        dayHeaderFormat: 'YYYY年M月D日 (ddd)',
                        agendaDateFormat: 'M/D (ddd)',
                        agendaTimeFormat: 'HH:mm',
                        agendaTimeRangeFormat: ({ start, end }) => `${dayjs(start).format('HH:mm')} - ${dayjs(end).format('HH:mm')}`,
                    }}
                />
            </div>

            <Modal
                title={currentBooking ? "编辑会议室预约" : "新建会议室预约"}
                visible={isModalVisible}
                onOk={handleOk}
                onCancel={() => setIsModalVisible(false)}
                footer={[
                    <Button key="back" onClick={() => setIsModalVisible(false)}>
                        取消
                    </Button>,
                    currentBooking && (isAdminOrManager || currentBooking.user.id === user.id) && (
                        <Popconfirm
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
        </div>
    );
};

export default MeetingRoomBookingPage;