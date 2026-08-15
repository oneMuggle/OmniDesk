/**
 * useUserManagementPage — UserManagementPage 主页面业务逻辑 HookLayer
 *
 * 由 UserManagementPage.jsx 拆分而来,承接用户/用户组/人员数据加载与更新:
 * 列表数据获取、用户组与人员关联更新。
 */
import { useEffect, useState } from 'react';
import { message } from 'antd';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../../personnel/api/personnelApi';
import { permissionsApi } from '../../../shared/api/permissionsApi';
import { useAuth } from '../../auth/context/AuthContext';
import { logger } from '../../../shared/utils/logger';

const useUserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState([]);
    const [groups, setGroups] = useState([]);
    const [personnel, setPersonnel] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchUsers = async () => {
        try {
            const res = await userManagementApi.getAllUsers();
            setUsers(res.data.results || []);
        } catch (error) {
            message.error('获取用户列表失败');
        }
    };

    const fetchGroups = async () => {
        try {
            const res = await permissionsApi.getGroups();
            setGroups(res.data.results || []);
        } catch (error) {
            message.error('获取用户组列表失败');
        }
    };

    const fetchPersonnel = async () => {
        try {
            const response = await getAllPersonnel();
            setPersonnel(response.data.results || []);
        } catch (error) {
            message.error('获取人员数据失败');
        }
    };

    // 初始加载:同步触发 loading 态(既有逻辑,自拆分前原文件逐字保留;
    // react-hooks/set-state-in-effect 规则新启用,行为优化留待后续)
    useEffect(() => {
        const fetchData = async () => {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setLoading(true);
            try {
                await Promise.all([fetchUsers(), fetchGroups(), fetchPersonnel()]);
            } catch (error) {
                logger.error("An error occurred during initial data fetch:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const handleGroupsChange = async (userId, groupIds) => {
        try {
            await userManagementApi.updateUserGroups(userId, groupIds);
            message.success('用户组更新成功');
            fetchUsers();
        } catch (error) {
            message.error('更新用户组失败');
        }
    };

    const handleAssociationChange = async (userId, personnelId) => {
        try {
          await userManagementApi.associateUserWithPersonnel(userId, personnelId);
          message.success('关联成功');
          fetchUsers(); // Refresh users to show updated data
        } catch (error) {
          message.error('关联失败');
        }
    };

    return {
        users, groups, personnel, loading,
        currentUserId: currentUser.id,
        fetchUsers, fetchGroups, fetchPersonnel,
        handleGroupsChange, handleAssociationChange,
    };
};

export default useUserManagementPage;
