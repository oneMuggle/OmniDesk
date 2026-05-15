import { useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import listPlugin from '@fullcalendar/list';
import dayjs from 'dayjs';
import { Modal, Button, Form, Input, DatePicker, Select, message, Popconfirm, notification, Spin, Descriptions } from 'antd';
import { CalendarOutlined, UserOutlined, PhoneOutlined } from '@ant-design/icons';
import { useAuth } from '../../auth/context/AuthContext';
import {
    useMeetingRooms,
    useMeetingRoomBookings,
    useCreateMeetingRoomBooking,
    useUpdateMeetingRoomBooking,
    useDeleteMeetingRoomBooking,
} from '../hooks/useMeetingRoomData';
import '../../../shared/components/styles/Schedule.css';
import './MeetingRoomBookingPage.css';

const { RangePicker } = DatePicker;
const { Option } = Select;
const { TextArea } = Input;

const MeetingRoomLegend = ({ meetingRooms, roomColorMap }) => (
    <div className="meeting-room-legend">
        <h4>会议室图例</h4>
        <div className="legend-items">
            {meetingRooms.map(room => (
                <div key={room.id} className="legend-item">
                    <span
                        className="legend-color-dot"
                        style={{ backgroundColor: roomColorMap.get(room.id) }}
                    />
                    <span className="legend-room-name">{room.name}</span>
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

    const handleSelect = ({ start, end }) => {
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
        if (dayjs(start).isBefore(dayjs())) {
            message.warning('无法预约过去的时间段。');
            return;
        }
        setCurrentBooking(null);
        form.resetFields();
        form.setFieldsValue({
            timeRange: [dayjs(start), dayjs(end)],
            meeting_room: meetingRooms.length > 0 ? meetingRooms[0].id : undefined
        });
        setIsModalVisible(true);
    };

    const handleEventClick = (clickInfo) => {
        const event = clickInfo.event;
        setSelectedEvent(event.extendedProps.rawBooking);
        setIsDetailModalVisible(true);
    };

    const handleEditEvent = () => {
        if (!selectedEvent) return;

        if (!isAdminOrManager && selectedEvent.user.id !== user.id) {
            message.warning('您没有权限编辑此预约。');
            return;
        }

        setIsDetailModalVisible(false);
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

    const eventDidMount = useCallback((info) => {
        const color = info.event.extendedProps.roomColor || '#6c757d';
        info.el.style.backgroundColor = color;
        info.el.style.borderRadius = '6px';
        info.el.style.border = 'none';
        info.el.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.12)';
        info.el.style.opacity = '0.9';
    }, []);

    const renderEventContent = (eventInfo) => {
        const { title, meetingRoomName } = eventInfo.event.extendedProps;
        return (
            <div className="fc-event-content" style={{ padding: '2px 4px', textAlign: 'center', width: '100%' }}>
                <div style={{ fontWeight: 'bold', fontSize: '0.85em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {title}
                </div>
                {meetingRoomName && (
                    <div style={{ fontSize: '0.75em', color: 'rgba(255, 255, 255, 0.85)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {meetingRoomName}
                    </div>
                )}
            </div>
        );
    };

    const calendarEvents = useMemo(() => {
        return bookings.map(booking => {
            const meetingRoom = meetingRooms.find(r => r.id === booking.meeting_room);
            return {
                id: String(booking.id),
                title: booking.title,
                start: booking.start,
                end: booking.end,
                allDay: false,
                extendedProps: {
                    roomColor: roomColorMap.get(booking.meeting_room) || '#6c757d',
                    meetingRoomName: meetingRoom?.name || '',
                    rawBooking: booking,
                },
            };
        });
    }, [bookings, meetingRooms, roomColorMap]);

    return (
        <div className="calendar-page-container">
            <div className="calendar-page-header">
                <h1>会议室预约</h1>
            </div>
            <Spin spinning={isLoading} tip="正在加载会议室数据...">
                <div className="calendar-page-content">
                    <div className="calendar-wrapper">
                        <FullCalendar
                            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin, listPlugin]}
                            initialView="timeGridWeek"
                            headerToolbar={{
                                left: 'prev,next today',
                                center: 'title',
                                right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
                            }}
                            locale="zh-cn"
                            buttonText={{
                                today: '今天',
                                month: '月',
                                week: '周',
                                day: '日',
                                list: '议程',
                            }}
                            slotMinTime="08:00:00"
                            slotMaxTime="22:00:00"
                            selectable={true}
                            select={handleSelect}
                            eventClick={handleEventClick}
                            events={calendarEvents}
                            eventDidMount={eventDidMount}
                            eventContent={renderEventContent}
                            firstDay={1}
                            height="auto"
                            dayMaxEvents={true}
                        />
                    </div>
                    <div className="calendar-sidebar">
                        <MeetingRoomLegend meetingRooms={meetingRooms} roomColorMap={roomColorMap} />
                    </div>
                </div>
            </Spin>

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
        </div>
    );
};

export default MeetingRoomBookingPage;
