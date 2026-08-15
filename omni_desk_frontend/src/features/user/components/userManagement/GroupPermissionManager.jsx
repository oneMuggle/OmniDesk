import PropTypes from 'prop-types';
import { Card, Col, Row } from 'antd';
import useGroupPermissionManager from '../../hooks/useGroupPermissionManager';
import GroupActionBar from './GroupActionBar';
import PermissionTreePanel from './PermissionTreePanel';
import GroupFormModal from './GroupFormModal';

/**
 * 用户组权限管理 — 权限矩阵组合组件。
 * 由 UserManagementPage.jsx 内同名子组件拆出,业务逻辑迁入
 * useGroupPermissionManager hook,展示拆为 GroupActionBar / PermissionTreePanel / GroupFormModal。
 */
const GroupPermissionManager = ({ groups, fetchGroups }) => {
    const {
        selectedGroupId, permissions, loading, checkedKeys, expandedKeys,
        searchValue, autoExpandParent, isModalVisible, editingGroup, form,
        setExpandedKeys,
        handleGroupChange, handleSavePermissions,
        onExpand, onCheck, onSearch,
        generatedTreeData, allKeys,
        showModal, handleCancel, handleOk, handleDelete,
    } = useGroupPermissionManager({ fetchGroups });

    return (
        <Card title="用户组权限管理">
            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <GroupActionBar
                        groups={groups}
                        selectedGroupId={selectedGroupId}
                        onGroupChange={handleGroupChange}
                        onCreate={() => showModal()}
                        onClickEdit={() => showModal(groups.find(g => g.id === selectedGroupId))}
                        onClickDelete={() => handleDelete(selectedGroupId)}
                        onSavePermissions={handleSavePermissions}
                    />
                </Col>
                <Col span={24}>
                    <PermissionTreePanel
                        permissions={permissions}
                        checkedKeys={checkedKeys}
                        expandedKeys={expandedKeys}
                        autoExpandParent={autoExpandParent}
                        loading={loading}
                        selectedGroupId={selectedGroupId}
                        allKeys={allKeys}
                        generatedTreeData={generatedTreeData}
                        onExpand={onExpand}
                        onCheck={onCheck}
                        onSearch={onSearch}
                        onExpandAll={() => setExpandedKeys(allKeys)}
                        onCollapseAll={() => setExpandedKeys([])}
                    />
                </Col>
            </Row>
            <GroupFormModal
                visible={isModalVisible}
                editingGroup={editingGroup}
                form={form}
                onOk={handleOk}
                onCancel={handleCancel}
            />
        </Card>
    );
};

GroupPermissionManager.propTypes = {
  groups: PropTypes.array.isRequired,
  fetchGroups: PropTypes.func.isRequired,
};

export default GroupPermissionManager;
