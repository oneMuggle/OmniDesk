import React, { useState, useEffect, useCallback } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, DatePicker, Select, Card, Statistic, Row, Col } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import meetingRoomApi from '../api/meetingRoomApi';
import dayjs from 'dayjs';
import { useAuth } from '../context/AuthContext';

const { RangePicker } = DatePicker;
const { Option } = Select;
const { TextArea } = Input;

const MeetingRoomManagementPage = () => {
    const { user } = useAuth(); // Keep user for isAdminOrManager check if needed elsewhere, otherwise remove.
    const [roomForm] = Form.useForm();
    const [maintenanceForm] = Form.useForm();
    const [isRoomModalVisible, setIsRoomModalVisible] = useState(false);
    const [isMaintenanceModalVisible, setIsMaintenanceModalVisible] = useState(false);
    const [editingRoom, setEditingRoom] = useState(null);
    const [editingMaintenance, setEditingMaintenance] = useState(null);
    const [meetingRooms, setMeetingRooms] = useState([]);
    const [maintenances, setMaintenances] = useState([]);
    const [stats, setStats] = useState({});
    const [statsFilter, setStatsFilter] = useState({
        startDate: dayjs().subtract(30, 'days'),
        endDate: dayjs(),
        meetingRoomId: null
    });
    const [loading, setLoading] = useState(false);

    const fetchMeetingRooms = useCallback(async () => {
        setLoading(true);
        try {
            const response = await meetingRoomApi.getMeetingRooms();
            console.log('Meeting Rooms API Response:', response);
            console.log('Meeting Rooms Data:', response.data);
            setMeetingRooms(response.data.results);
        } catch (error) {
            message.error('获取会议室列表失败。');
            console.error('Failed to fetch meeting rooms:', error.response || error);
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchMaintenances = useCallback(async () => {
        setLoading(true);
        try {
            const response = await meetingRoomApi.getMeetingRoomMaintenances();
            setMaintenances(response.data.results.map(m => ({
                ...m,
                start: new Date(m.start_time),
                end: new Date(m.end_time)
            })));
        } catch (error) {
            message.error('获取维护记录失败。');
            console.error('Failed to fetch maintenances:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const params = {
                start_date: statsFilter.startDate.format('YYYY-MM-DD'),
                end_date: statsFilter.endDate.format('YYYY-MM-DD'),
            };
            if (statsFilter.meetingRoomId) {
                params.meeting_room_id = statsFilter.meetingRoomId;
            }
            const response = await meetingRoomApi.getMeetingRoomStats(params);
            setStats(response.data);
        } catch (error) {
            message.error('获取统计数据失败。');
            console.error('Failed to fetch stats:', error);
        } finally {
            setLoading(false);
        }
    }, [statsFilter]);

    useEffect(() => {
        fetchMeetingRooms();
        fetchMaintenances();
        fetchStats();
    }, [fetchMeetingRooms, fetchMaintenances, fetchStats]);

    // Meeting Room Management
    const handleAddRoom = () => {
        setEditingRoom(null);
        roomForm.resetFields();
        setIsRoomModalVisible(true);
    };

    const handleEditRoom = (record) => {
        setEditingRoom(record);
        roomForm.setFieldsValue(record);
        setIsRoomModalVisible(true);
    };

    const handleSaveRoom = async () => {
        try {
            const values = await roomForm.validateFields();
            if (editingRoom) {
                await meetingRoomApi.updateMeetingRoom(editingRoom.id, values);
                message.success('会议室更新成功！');
            } else {
                await meetingRoomApi.createMeetingRoom(values);
                message.success('会议室添加成功！');
            }
            setIsRoomModalVisible(false);
            fetchMeetingRooms();
        } catch (error) {
            const errorMsg = error.response?.data?.name?.[0] || '操作失败，请重试。';
            message.error(errorMsg);
            console.error('Failed to save room:', error);
        }
    };

    const handleDeleteRoom = async (id) => {
        try {
            await meetingRoomApi.deleteMeetingRoom(id);
            message.success('会议室删除成功！');
            fetchMeetingRooms();
        } catch (error) {
            message.error('删除会议室失败。');
            console.error('Failed to delete room:', error);
        }
    };

    const roomColumns = [
        { title: '名称', dataIndex: 'name', key: 'name' },
        { title: '描述', dataIndex: 'description', key: 'description' },
        { title: '容量', dataIndex: 'capacity', key: 'capacity' },
        { title: '位置', dataIndex: 'location', key: 'location' },
        {
            title: '操作',
            key: 'actions',
            render: (text, record) => (
                <span>
                    <Button icon={<EditOutlined />} onClick={() => handleEditRoom(record)} style={{ marginRight: 8 }} />
                    <Popconfirm title="确定删除此会议室吗？" onConfirm={() => handleDeleteRoom(record.id)}>
                        <Button icon={<DeleteOutlined />} danger />
                    </Popconfirm>
                </span>
            ),
        },
    ];

    // Maintenance Management
    const handleAddMaintenance = () => {
        setEditingMaintenance(null);
        maintenanceForm.resetFields();
        setIsMaintenanceModalVisible(true);
    };

    const handleEditMaintenance = (record) => {
        setEditingMaintenance(record);
        maintenanceForm.setFieldsValue({
            meeting_room: record.meeting_room,
            timeRange: [dayjs(record.start_time), dayjs(record.end_time)],
            reason: record.reason,
        });
        setIsMaintenanceModalVisible(true);
    };

    const handleSaveMaintenance = async () => {
        try {
            const values = await maintenanceForm.validateFields();
            const [start_time, end_time] = values.timeRange;
            const maintenanceData = {
                meeting_room: values.meeting_room,
                start_time: start_time.toISOString(),
                end_time: end_time.toISOString(),
                reason: values.reason,
            };

            if (editingMaintenance) {
                await meetingRoomApi.updateMeetingRoomMaintenance(editingMaintenance.id, maintenanceData);
                message.success('维护记录更新成功！');
            } else {
                await meetingRoomApi.createMeetingRoomMaintenance(maintenanceData);
                message.success('维护记录添加成功！');
            }
            setIsMaintenanceModalVisible(false);
            fetchMaintenances();
        } catch (error) {
            const errorMsg = error.response?.data?.non_field_errors?.[0] || '操作失败，请重试。';
            message.error(errorMsg);
            console.error('Failed to save maintenance:', error);
        }
    };

    const handleDeleteMaintenance = async (id) => {
        try {
            await meetingRoomApi.deleteMeetingRoomMaintenance(id);
            message.success('维护记录删除成功！');
            fetchMaintenances();
        } catch (error) {
            message.error('删除维护记录失败。');
            console.error('Failed to delete maintenance:', error);
        }
    };

    const maintenanceColumns = [
        { title: '会议室', dataIndex: 'meeting_room_name', key: 'meeting_room_name' },
        { title: '开始时间', dataIndex: 'start_time', key: 'start_time', render: (text) => dayjs(text).format('YYYY-MM-DD HH:mm') },
        { title: '结束时间', dataIndex: 'end_time', key: 'end_time', render: (text) => dayjs(text).format('YYYY-MM-DD HH:mm') },
        { title: '原因', dataIndex: 'reason', key: 'reason' },
        {
            title: '操作',
            key: 'actions',
            render: (text, record) => (
                <span>
                    <Button icon={<EditOutlined />} onClick={() => handleEditMaintenance(record)} style={{ marginRight: 8 }} />
                    <Popconfirm title="确定删除此维护记录吗？" onConfirm={() => handleDeleteMaintenance(record.id)}>
                        <Button icon={<DeleteOutlined />} danger />
                    </Popconfirm>
                </span>
            ),
        },
    ];

    // Stats Management
    const handleStatsFilterChange = (dates, dateStrings) => {
        setStatsFilter(prev => ({
            ...prev,
            startDate: dates ? dates[0] : null,
            endDate: dates ? dates[1] : null,
        }));
    };

    const handleMeetingRoomFilterChange = (value) => {
        setStatsFilter(prev => ({
            ...prev,
            meetingRoomId: value,
        }));
    };

    const totalDurationHours = stats.total_booking_duration_minutes ? (stats.total_booking_duration_minutes / 60).toFixed(2) : 0;

    return (
        <div style={{ padding: '20px' }}>
            <h1>会议室管理</h1>

            <Card title="会议室列表" extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAddRoom}>添加会议室</Button>} style={{ marginBottom: 20 }}>
                <Table
                    columns={roomColumns}
                    dataSource={meetingRooms}
                    rowKey="id"
                    loading={loading}
                    pagination={false}
                />
            </Card>

            <Modal
                title={editingRoom ? "编辑会议室" : "添加会议室"}
                visible={isRoomModalVisible}
                onOk={handleSaveRoom}
                onCancel={() => setIsRoomModalVisible(false)}
                confirmLoading={loading}
            >
                <Form form={roomForm} layout="vertical">
                    <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入会议室名称!' }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="description" label="描述">
                        <TextArea rows={2} />
                    </Form.Item>
                    <Form.Item name="capacity" label="容量">
                        <Input type="number" />
                    </Form.Item>
                    <Form.Item name="location" label="位置">
                        <Input />
                    </Form.Item>
                </Form>
            </Modal>

            <Card title="会议室维护管理" extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAddMaintenance}>添加维护记录</Button>} style={{ marginBottom: 20 }}>
                <Table
                    columns={maintenanceColumns}
                    dataSource={maintenances}
                    rowKey="id"
                    loading={loading}
                    pagination={false}
                />
            </Card>

            <Modal
                title={editingMaintenance ? "编辑维护记录" : "添加维护记录"}
                visible={isMaintenanceModalVisible}
                onOk={handleSaveMaintenance}
                onCancel={() => setIsMaintenanceModalVisible(false)}
                confirmLoading={loading}
            >
                <Form form={maintenanceForm} layout="vertical">
                    <Form.Item name="meeting_room" label="会议室" rules={[{ required: true, message: '请选择会议室!' }]}>
                        <Select placeholder="选择会议室">
                            {meetingRooms.map(room => (
                                <Option key={room.id} value={room.id}>{room.name}</Option>
                            ))}
                        </Select>
                    </Form.Item>
                    <Form.Item name="timeRange" label="维护时间范围" rules={[{ required: true, message: '请选择维护时间范围!' }]}>
                        <RangePicker
                            showTime={{ format: 'HH:mm' }}
                            format="YYYY-MM-DD HH:mm"
                            style={{ width: '100%' }}
                        />
                    </Form.Item>
                    <Form.Item name="reason" label="维护原因" rules={[{ required: true, message: '请输入维护原因!' }]}>
                        <Input />
                    </Form.Item>
                </Form>
            </Modal>

            <Card title="会议室使用统计" style={{ marginBottom: 20 }}>
                <Row gutter={16} align="middle" style={{ marginBottom: 20 }}>
                    <Col>
                        <RangePicker
                            value={[statsFilter.startDate, statsFilter.endDate]}
                            onChange={handleStatsFilterChange}
                            format="YYYY-MM-DD"
                        />
                    </Col>
                    <Col>
                        <Select
                            placeholder="选择会议室"
                            allowClear
                            style={{ width: 150 }}
                            onChange={handleMeetingRoomFilterChange}
                            value={statsFilter.meetingRoomId}
                        >
                            {meetingRooms.map(room => (
                                <Option key={room.id} value={room.id}>{room.name}</Option>
                            ))}
                        </Select>
                    </Col>
                    <Col>
                        <Button type="primary" onClick={fetchStats} loading={loading}>刷新统计</Button>
                    </Col>
                </Row>
                <Row gutter={16}>
                    <Col span={8}>
                        <Card>
                            <Statistic title="总预约数量" value={stats.total_bookings || 0} />
                        </Card>
                    </Col>
                    <Col span={8}>
                        <Card>
                            <Statistic title="总预约时长 (小时)" value={totalDurationHours} precision={2} />
                        </Card>
                    </Col>
                </Row>
                {stats.room_stats && stats.room_stats.length > 0 && (
                    <div style={{ marginTop: 20 }}>
                        <h3>各会议室使用情况</h3>
                        <Table
                            columns={[
                                { title: '会议室', dataIndex: 'meeting_room_name', key: 'name' },
                                { title: '预约次数', dataIndex: 'booking_count', key: 'count' },
                                { title: '总时长 (小时)', dataIndex: 'total_duration_minutes', key: 'duration', render: (text) => (text / 60).toFixed(2) },
                            ]}
                            dataSource={stats.room_stats}
                            rowKey="meeting_room_name"
                            pagination={false}
                            loading={loading}
                        />
                    </div>
                )}
            </Card>
        </div>
    );
};

export default MeetingRoomManagementPage;