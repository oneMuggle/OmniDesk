import PropTypes from 'prop-types';
import { Form, Input, Modal } from 'antd';

/**
 * 用户组新增/编辑 Modal — 共享同一表单,按 editingGroup 切换标题。
 * 由 GroupPermissionManager 拆出,原 JSX 逐字搬入。
 */
const GroupFormModal = ({ visible, editingGroup, form, onOk, onCancel }) => (
    <Modal
        title={editingGroup ? '编辑用户组' : '新增用户组'}
        open={visible}
        onOk={onOk}
        onCancel={onCancel}
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
);

GroupFormModal.propTypes = {
    visible: PropTypes.bool,
    editingGroup: PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        name: PropTypes.string,
    }),
    form: PropTypes.object.isRequired,
    onOk: PropTypes.func.isRequired,
    onCancel: PropTypes.func.isRequired,
};

export default GroupFormModal;
