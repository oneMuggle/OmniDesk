import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient'; // 导入 apiClient
import { toast } from 'react-toastify';
import { useAuth } from '../context/AuthContext'; // 假设有 AuthContext 用于获取 token

const UserPersonnelManagementPage = () => {
    const [users, setUsers] = useState([]);
    const [personnel, setPersonnel] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const { isAuthenticated } = useAuth(); // 仅使用 isAuthenticated 状态，不再直接获取 authToken

    useEffect(() => {
        const fetchData = async () => {
            if (!isAuthenticated) { // 如果未认证，则不发送请求
                setLoading(false);
                setError('请登录以查看人员管理信息。');
                return;
            }
            try {
                // apiClient 已经自动处理了 Authorization 头，无需手动添加
                const [usersResponse, personnelResponse] = await Promise.all([
                    apiClient.get('/users/'), // 获取所有用户，用于指派人下拉列表
                    apiClient.get('/users/personnel/') // 获取所有人员，即所有CustomUser
                ]);
                setUsers(usersResponse.data.results || usersResponse.data); // 假设 users 也可能是分页数据
                setPersonnel(personnelResponse.data.results || personnelResponse.data);
            } catch (err) {
                setError('加载数据失败。请稍后重试。');
                toast.error('加载数据失败。');
                console.error('Error fetching data:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isAuthenticated]); // 依赖 isAuthenticated 状态

    const handleAssignedByChange = async (personnelId, newAssignedById) => {
        try {
            // apiClient 已经自动处理了 Authorization 头，无需手动添加
            await apiClient.patch(`/users/personnel/${personnelId}/`, { assigned_by: newAssignedById || null });
            setPersonnel(prevPersonnel =>
                prevPersonnel.map(p =>
                    p.id === personnelId ? { ...p, assigned_by: newAssignedById, assigned_by_username: users.find(u => u.id === newAssignedById)?.username || null } : p
                )
            );
            toast.success('关联更新成功！');
        } catch (err) {
            toast.error('更新关联失败。');
            console.error('Error updating assignment:', err);
        }
    };

    if (loading) return <div>加载中...</div>;
    if (error) return <div>{error}</div>;

    return (
        <div className="user-personnel-management-page">
            <h1>用户人员关联管理</h1>
            <table>
                <thead>
                    <tr>
                        <th>用户名</th>
                        <th>角色</th>
                        <th>当前指派人</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {personnel.map(p => (
                        <tr key={p.id}>
                            <td>{p.username}</td>
                            <td>{p.role}</td>
                            <td>{p.assigned_by_username || '未指派'}</td>
                            <td>
                                <select
                                    value={p.assigned_by || ''}
                                    onChange={(e) => handleAssignedByChange(p.id, e.target.value ? parseInt(e.target.value) : null)}
                                >
                                    <option value="">-- 选择指派人 --</option>
                                    {users.map(u => (
                                        <option key={u.id} value={u.id}>
                                            {u.username} ({u.role})
                                        </option>
                                    ))}
                                </select>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default UserPersonnelManagementPage;