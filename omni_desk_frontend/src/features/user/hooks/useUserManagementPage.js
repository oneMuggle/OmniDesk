/**
 * useUserManagementPage — UserManagementPage 主页面业务逻辑 HookLayer
 *
 * 由 UserManagementPage.jsx 拆分而来,承接用户/用户组/人员数据加载与更新:
 * 列表数据获取、用户组与人员关联更新。
 * R5-D6:数据来源切换为 useCrudQuery(React Query),增删改后的手动刷新
 * 换为 invalidateQueries;对外返回接口保持不变。
 */
import { useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import userManagementApi from '../api/userManagementApi';
import { getAllPersonnel } from '../../personnel/api/personnelApi';
import { permissionsApi } from '../../../shared/api/permissionsApi';
import { useAuth } from '../../auth/context/AuthContext';
import { useCrudQuery } from '../../../shared/hooks/useCrudQuery';

// 与原实现等价的错误文案(useCrudQuery 默认文案不同,故逐项显式指定)
const USERS_ERROR = '获取用户列表失败';
const GROUPS_ERROR = '获取用户组列表失败';
const PERSONNEL_ERROR = '获取人员数据失败';

const usersFetcher = async () => {
    const res = await userManagementApi.getAllUsers();
    return res.data;
};

const groupsFetcher = async () => {
    const res = await permissionsApi.getGroups();
    return res.data;
};

const personnelFetcher = async () => {
    const response = await getAllPersonnel();
    return response.data;
};

const useUserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const queryClient = useQueryClient();

    const usersQuery = useCrudQuery(['user-management', 'users'], usersFetcher, {
        errorMessage: USERS_ERROR,
    });
    const groupsQuery = useCrudQuery(['user-management', 'groups'], groupsFetcher, {
        errorMessage: GROUPS_ERROR,
    });
    const personnelQuery = useCrudQuery(['user-management', 'personnel'], personnelFetcher, {
        errorMessage: PERSONNEL_ERROR,
    });

    // 列表刷新(增删改后调用),等价于原手动 fetchUsers/fetchGroups/fetchPersonnel
    const invalidateList = (key) => queryClient.invalidateQueries({ queryKey: key });

    const fetchUsers = () => invalidateList(['user-management', 'users']);
    const fetchGroups = () => invalidateList(['user-management', 'groups']);
    const fetchPersonnel = () => invalidateList(['user-management', 'personnel']);

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
        users: usersQuery.data ?? [],
        groups: groupsQuery.data ?? [],
        personnel: personnelQuery.data ?? [],
        loading: usersQuery.isLoading || groupsQuery.isLoading || personnelQuery.isLoading,
        currentUserId: currentUser.id,
        fetchUsers, fetchGroups, fetchPersonnel,
        handleGroupsChange, handleAssociationChange,
    };
};

export default useUserManagementPage;
