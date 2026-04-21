import React, { useState, useEffect } from 'react';
import { Table, Tag, Typography, Space } from 'antd';
import { format } from 'date-fns';
import complianceApi from '../api/compliance';

const { Title } = Typography;

const NotificationsPage = () => {
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchNotifications = async () => {
            try {
                setLoading(true);
                const response = await complianceApi.getAllComplianceIssues();
                setNotifications(response.data.results || response.data);
                setLoading(false);
            } catch (err) {
                setError('无法加载通知，请稍后再试。');
                console.error('Error fetching notifications:', err);
                setLoading(false);
            }
        };

        fetchNotifications();
    }, []);

    const getSeverityColor = (severity) => {
        switch (severity) {
            case '紧急': return 'red';
            case '高': return 'orange';
            default: return 'default';
        }
    };

    const columns = [
        { title: '问题类型', dataIndex: 'issue_type', key: 'issue_type' },
        { title: '描述', dataIndex: 'description', key: 'description' },
        { title: '项目', dataIndex: 'project_name', key: 'project_name' },
        { title: '关联文档', key: 'document', render: (_, record) => record.document_book_title || record.document_template_name || 'N/A' },
        { title: '位置', dataIndex: 'location', key: 'location' },
        { title: '严重程度', dataIndex: 'severity', key: 'severity', render: (severity) => <Tag color={getSeverityColor(severity)}>{severity}</Tag> },
        { title: '状态', dataIndex: 'status', key: 'status' },
        { title: '截止日期', dataIndex: 'due_date', key: 'due_date', render: (date) => date ? format(new Date(date), 'yyyy-MM-dd') : 'N/A' },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (date) => format(new Date(date), 'yyyy-MM-dd HH:mm') },
    ];

    if (loading) {
        return <div style={{ padding: '24px' }}><Typography>正在加载通知...</Typography></div>;
    }

    if (error) {
        return <div style={{ padding: '24px' }}><Typography color="error">{error}</Typography></div>;
    }

    return (
        <div style={{ padding: '24px' }}>
            <Title level={2}>通知中心</Title>
            <Table
                columns={columns}
                dataSource={notifications.map(n => ({ ...n, key: n.id }))}
                loading={loading}
                pagination={{ pageSize: 10 }}
            />
        </div>
    );
};

export default NotificationsPage;
