/**
 * useGroupPermissionManager — 用户组权限矩阵 HookLayer
 *
 * 由 UserManagementPage.jsx 内 GroupPermissionManager 子组件拆分而来,
 * 承接组 CRUD + 权限树加载/搜索/勾选/保存 + 新增编辑 Modal 全部业务逻辑。
 */
import { useEffect, useMemo, useState } from 'react';
import { Form, message, Modal } from 'antd';
import userManagementApi from '../api/userManagementApi';
import { permissionsApi } from '../../../shared/api/permissionsApi';
import { getAllKeys } from '../utils/userManagementUtils';

const useGroupPermissionManager = ({ fetchGroups }) => {
    const [selectedGroupId, setSelectedGroupId] = useState(null);
    const [permissions, setPermissions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [checkedKeys, setCheckedKeys] = useState([]);
    const [expandedKeys, setExpandedKeys] = useState([]);
    const [searchValue, setSearchValue] = useState('');
    const [autoExpandParent, setAutoExpandParent] = useState(true);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingGroup, setEditingGroup] = useState(null);
    const [form] = Form.useForm();

    useEffect(() => {
        // eslint-disable-next-line react-hooks/immutability
        fetchPermissions();
    }, []);

    useEffect(() => {
        if (selectedGroupId) {
            // eslint-disable-next-line react-hooks/immutability
            fetchGroupPermissions(selectedGroupId);
        } else {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setCheckedKeys([]);
        }
    }, [selectedGroupId]);

    const fetchPermissions = async () => {
        try {
            const res = await userManagementApi.getGroupedPermissions();
            const data = res.data;
            const formattedTreeData = Object.keys(data).map(groupName => ({
                title: groupName,
                key: groupName,
                children: (data[groupName] || []).map(perm => ({
                    title: perm.name,
                    key: perm.id,
                })),
            }));
            setPermissions(formattedTreeData);
        } catch (error) {
            message.error('获取权限列表失败');
        }
    };

    const fetchGroupPermissions = async (groupId) => {
        setLoading(true);
        try {
            const res = await userManagementApi.getGroupPermissions(groupId);
            setCheckedKeys(res.data.permissions || []);
        } catch (error) {
            message.error('获取用户组权限失败');
        } finally {
            setLoading(false);
        }
    };

    const handleGroupChange = (groupId) => {
        setSelectedGroupId(groupId);
    };

    const handleSavePermissions = async () => {
        if (!selectedGroupId) {
            message.warn('请先选择一个用户组');
            return;
        }
        setLoading(true);
        try {
            await userManagementApi.updateGroupPermissions(selectedGroupId, checkedKeys);
            message.success('权限更新成功');
        } catch (error) {
            message.error('权限更新失败');
        } finally {
            setLoading(false);
        }
    };

    const onExpand = (newExpandedKeys) => {
        setExpandedKeys(newExpandedKeys);
        setAutoExpandParent(false);
    };

    const onCheck = (checked) => {
        setCheckedKeys(checked);
    };

    const onSearch = (e) => {
        const { value } = e.target;
        const newExpandedKeys = permissions
            .map((item) => {
                if (item.children.some(child => child.title.toLowerCase().includes(value.toLowerCase()))) {
                    return item.key;
                }
                return null;
            })
            .filter((item, i, self) => item && self.indexOf(item) === i);

        setExpandedKeys(newExpandedKeys);
        setSearchValue(value);
        setAutoExpandParent(true);
    };

    const generatedTreeData = useMemo(() => {
        const loop = (data) =>
            data.map((item) => {
                const strTitle = item.title;
                const index = strTitle.toLowerCase().indexOf(searchValue.toLowerCase());
                const beforeStr = strTitle.substring(0, index);
                const afterStr = strTitle.slice(index + searchValue.length);
                const title =
                    index > -1 ? (
                        <span>
                            {beforeStr}
                            <span style={{ color: '#f50' }}>{strTitle.substring(index, index + searchValue.length)}</span>
                            {afterStr}
                        </span>
                    ) : (
                        <span>{strTitle}</span>
                    );
                if (item.children) {
                    return { title: item.title, key: item.key, children: loop(item.children) };
                }
                return {
                    title,
                    key: item.key,
                };
            });

        if (!searchValue) {
            return permissions;
        }
        const filteredData = permissions.map(group => {
            const filteredChildren = group.children.filter(perm => perm.title.toLowerCase().includes(searchValue.toLowerCase()));
            if (filteredChildren.length > 0) {
                return { ...group, children: loop(filteredChildren) };
            }
            return null;
        }).filter(Boolean);

        return loop(filteredData);
    }, [searchValue, permissions]);

    const allKeys = useMemo(() => getAllKeys(permissions), [permissions]);

    const showModal = (group = null) => {
        setEditingGroup(group);
        form.setFieldsValue({ name: group ? group.name : '' });
        setIsModalVisible(true);
    };

    const handleCancel = () => {
        setIsModalVisible(false);
        setEditingGroup(null);
        form.resetFields();
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            if (editingGroup) {
                await permissionsApi.updateGroup(editingGroup.id, values);
                message.success('用户组更新成功');
            } else {
                await permissionsApi.createGroup(values);
                message.success('用户组创建成功');
            }
            fetchGroups();
            handleCancel();
        } catch (error) {
            message.error('操作失败');
        }
    };

    const handleDelete = (groupId) => {
        Modal.confirm({
            title: '确定要删除这个用户组吗？',
            content: '删除后，该用户组的权限配置将一并被移除。',
            okText: '确定',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                try {
                    await permissionsApi.deleteGroup(groupId);
                    message.success('用户组删除成功');
                    if (selectedGroupId === groupId) {
                        setSelectedGroupId(null);
                    }
                    fetchGroups();
                } catch (error) {
                    message.error('删除失败');
                }
            },
        });
    };

    return {
        selectedGroupId, permissions, loading, checkedKeys, expandedKeys,
        searchValue, autoExpandParent, isModalVisible, editingGroup, form,
        setExpandedKeys,
        handleGroupChange, handleSavePermissions,
        onExpand, onCheck, onSearch,
        generatedTreeData, allKeys,
        showModal, handleCancel, handleOk, handleDelete,
    };
};

export default useGroupPermissionManager;
