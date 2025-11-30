import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout, List, Tree, Button, message, Spin, Card, Typography, Modal, Form, Input, Space
} from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { permissionsApi } from '../../api/permissionsApi';

const { Sider, Content } = Layout;
const { Title } = Typography;

const GroupPermissionManager = () => {
  const [groups, setGroups] = useState([]);
  const [pageTree, setPageTree] = useState([]);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [checkedKeys, setCheckedKeys] = useState([]);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadingTree, setLoadingTree] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [form] = Form.useForm();

  const fetchGroups = useCallback(async () => {
    setLoadingGroups(true);
    try {
      const response = await permissionsApi.getGroups();
      setGroups(response.results);
      if (response.results.length > 0 && !selectedGroupId) {
        setSelectedGroupId(response.results[0].id);
      }
    } catch (error) {
      message.error('获取用户组列表失败');
    } finally {
      setLoadingGroups(false);
    }
  }, [selectedGroupId]);

  const fetchPageTree = useCallback(async () => {
    setLoadingTree(true);
    try {
      const response = await permissionsApi.getPageTree();
      const addKeys = (nodes) => nodes.map(node => ({
        ...node,
        key: node.id,
        title: node.name,
        children: node.children ? addKeys(node.children) : [],
      }));
      setPageTree(addKeys(response.results));
    } catch (error) {
      message.error('获取页面权限树失败');
    } finally {
      setLoadingTree(false);
    }
  }, []);

  useEffect(() => {
    fetchGroups();
    fetchPageTree();
  }, [fetchGroups, fetchPageTree]);

  useEffect(() => {
    if (selectedGroupId) {
      setLoadingTree(true);
      permissionsApi.getGroupPermissions(selectedGroupId)
        .then(data => {
          // The API returns a flat array of IDs, which is exactly what checkedKeys needs.
          // The previous .map(p => p.id) was incorrect as it operated on an array of numbers.
          setCheckedKeys(data);
        })
        .catch(() => {
          message.error('获取用户组权限失败');
        })
        .finally(() => {
          setLoadingTree(false);
        });
    }
  }, [selectedGroupId]);

  const handleGroupSelect = (groupId) => {
    setSelectedGroupId(groupId);
  };

  const onCheck = (checkedKeysValue) => {
    // Antd's Tree's onCheck can return an object {checked: [], halfChecked: []}
    // or just an array. We only want the checked keys.
    if (Array.isArray(checkedKeysValue)) {
      setCheckedKeys(checkedKeysValue);
    } else {
      setCheckedKeys(checkedKeysValue.checked);
    }
  };

  const handleSave = async () => {
    if (!selectedGroupId) {
      message.warn('请先选择一个用户组');
      return;
    }
    setSaving(true);
    try {
      // Ensure we are sending a flat array of keys.
      const keysToSend = Array.isArray(checkedKeys) ? checkedKeys : checkedKeys.checked;
      await permissionsApi.updateGroupPermissions(selectedGroupId, keysToSend);
      message.success('权限更新成功');
    } catch (error) {
      message.error('权限更新失败');
    } finally {
      setSaving(false);
    }
  };

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
          // After deletion, refetch groups and reset selection if needed
          const currentSelectedId = selectedGroupId;
          if (currentSelectedId === groupId) {
            setSelectedGroupId(null);
          }
          fetchGroups();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };
  
  const selectedGroup = groups.find(g => g.id === selectedGroupId);

  return (
    <Layout style={{ background: '#fff' }}>
      <Sider width={300} style={{ background: '#fff', borderRight: '1px solid #f0f0f0', paddingRight: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={5} style={{ margin: 0 }}>用户组</Title>
          <Button icon={<PlusOutlined />} onClick={() => showModal()} />
        </div>
        <Spin spinning={loadingGroups}>
          <List
            dataSource={groups}
            renderItem={item => (
              <List.Item
                onClick={() => handleGroupSelect(item.id)}
                style={{
                  cursor: 'pointer',
                  backgroundColor: selectedGroupId === item.id ? '#e6f7ff' : 'transparent',
                  padding: '8px 16px',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}
              >
                <span>{item.name}</span>
                <Space>
                  <Button type="text" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); showModal(item); }} />
                  <Button type="text" danger icon={<DeleteOutlined />} onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }} />
                </Space>
              </List.Item>
            )}
            rowKey="id"
          />
        </Spin>
      </Sider>
      <Content style={{ padding: '0 24px', minHeight: 280 }}>
        <Spin spinning={loadingTree || saving}>
          <Title level={5}>
            权限配置 {selectedGroup ? `- ${selectedGroup.name}` : ''}
          </Title>
          {pageTree.length > 0 ? (
            <Tree
              checkable
              onCheck={onCheck}
              checkedKeys={checkedKeys}
              treeData={pageTree}
              defaultExpandAll
            />
          ) : (
            <p>暂无权限数据</p>
          )}
          <Button
            type="primary"
            onClick={handleSave}
            disabled={!selectedGroupId || saving}
            style={{ marginTop: 24 }}
          >
            {saving ? '保存中...' : '保存'}
          </Button>
        </Spin>
      </Content>
      <Modal
        title={editingGroup ? '编辑用户组' : '新增用户组'}
        visible={isModalVisible}
        onOk={handleOk}
        onCancel={handleCancel}
        okText="确定"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" name="group_form">
          <Form.Item
            name="name"
            label="用户组名称"
            rules={[{ required: true, message: '请输入用户组名称' }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
};

export default GroupPermissionManager;