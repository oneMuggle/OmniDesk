import PropTypes from 'prop-types';
import { Button, Card, Input, Space, Spin, Tree } from 'antd';

const { Search } = Input;

/**
 * 权限树面板 — 用户组权限矩阵的权限树展示 + 全部展开/折叠 + 搜索高亮。
 * 由 GroupPermissionManager 拆出,原 JSX 逐字搬入。
 */
const PermissionTreePanel = ({
    checkedKeys,
    expandedKeys,
    autoExpandParent,
    loading,
    selectedGroupId,
    generatedTreeData,
    onExpand,
    onCheck,
    onSearch,
    onExpandAll,
    onCollapseAll,
}) => (
    <Spin spinning={loading}>
        <Card>
            <Space style={{ marginBottom: 16 }}>
                <Button onClick={onExpandAll}>全部展开</Button>
                <Button onClick={onCollapseAll}>全部折叠</Button>
                <Search placeholder="搜索权限" onChange={onSearch} style={{ width: 300 }} />
            </Space>
            {selectedGroupId ? (
                <Tree
                    checkable
                    onExpand={onExpand}
                    expandedKeys={expandedKeys}
                    autoExpandParent={autoExpandParent}
                    onCheck={onCheck}
                    checkedKeys={checkedKeys}
                    treeData={generatedTreeData}
                />
            ) : (
                <p>请先选择一个用户组以配置权限。</p>
            )}
        </Card>
    </Spin>
);

PermissionTreePanel.propTypes = {
    checkedKeys: PropTypes.oneOfType([PropTypes.array, PropTypes.object]),
    expandedKeys: PropTypes.array,
    autoExpandParent: PropTypes.bool,
    loading: PropTypes.bool,
    selectedGroupId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    generatedTreeData: PropTypes.array,
    onExpand: PropTypes.func.isRequired,
    onCheck: PropTypes.func.isRequired,
    onSearch: PropTypes.func.isRequired,
    onExpandAll: PropTypes.func.isRequired,
    onCollapseAll: PropTypes.func.isRequired,
};

export default PermissionTreePanel;
