import React, { useState, useEffect } from 'react';
import { Container, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper, Chip } from '@mui/material';
import { format } from 'date-fns';
import complianceApi from '../api/compliance'; // 导入合规API

const NotificationsPage = () => {
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchNotifications();
    }, []);

    const fetchNotifications = async () => {
        try {
            setLoading(true);
            const response = await complianceApi.getAllComplianceIssues();
            setNotifications(response.data.results || response.data); // 假设返回的数据结构
            setLoading(false);
        } catch (err) {
            setError('无法加载通知，请稍后再试。');
            console.error('Error fetching notifications:', err);
            setLoading(false);
        }
    };

    if (loading) {
        return <Container><Typography>正在加载通知...</Typography></Container>;
    }

    if (error) {
        return <Container><Typography color="error">{error}</Typography></Container>;
    }

    return (
        <Container>
            <Typography variant="h4" component="h1" gutterBottom>
                通知中心
            </Typography>
            <Paper style={{ marginTop: '20px' }}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>问题类型</TableCell>
                            <TableCell>描述</TableCell>
                            <TableCell>项目</TableCell>
                            <TableCell>关联文档</TableCell>
                            <TableCell>位置</TableCell>
                            <TableCell>严重程度</TableCell>
                            <TableCell>状态</TableCell>
                            <TableCell>截止日期</TableCell>
                            <TableCell>创建时间</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {notifications.length > 0 ? (
                            notifications.map((notification) => (
                                <TableRow key={notification.id}>
                                    <TableCell>{notification.issue_type}</TableCell>
                                    <TableCell>{notification.description}</TableCell>
                                    <TableCell>{notification.project_name}</TableCell>
                                    <TableCell>
                                        {notification.document_book_title || notification.document_template_name || 'N/A'}
                                    </TableCell>
                                    <TableCell>{notification.location}</TableCell>
                                    <TableCell>
                                        <Chip
                                            label={notification.severity}
                                            color={
                                                notification.severity === '紧急' ? 'error' :
                                                notification.severity === '高' ? 'warning' :
                                                'default'
                                            }
                                        />
                                    </TableCell>
                                    <TableCell>{notification.status}</TableCell>
                                    <TableCell>
                                        {notification.due_date ? format(new Date(notification.due_date), 'yyyy-MM-dd') : 'N/A'}
                                    </TableCell>
                                    <TableCell>
                                        {format(new Date(notification.created_at), 'yyyy-MM-dd HH:mm')}
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={9} align="center">
                                    暂无通知。
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </Paper>
        </Container>
    );
};

export default NotificationsPage;