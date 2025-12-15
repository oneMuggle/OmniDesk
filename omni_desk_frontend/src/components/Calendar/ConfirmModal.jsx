import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Modal, Button } from 'antd';

const ConfirmModal = (props) => {
  const {
    title = '确认操作',
    content = '确定要执行此操作吗？',
    okText = '确定',
    cancelText = '取消',
    onOk,
    onCancel,
    okButtonProps = {},
    danger = false,
    open,
  } = props;
  const [confirmLoading, setConfirmLoading] = useState(false);

  const handleOk = async () => {
    setConfirmLoading(true);
    try {
      await onOk?.();
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancel = () => {
    onCancel?.();
  };

  return (
    <Modal
      title={title}
      open={open}
      getContainer={false}
      onOk={handleOk}
      confirmLoading={confirmLoading}
      onCancel={handleCancel}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          {cancelText}
        </Button>,
        <Button
          key="ok"
          type={danger ? 'primary' : 'default'}
          danger={danger}
          loading={confirmLoading}
          onClick={handleOk}
          {...okButtonProps}
          data-testid={props['data-testid'] ? `${props['data-testid']}-ok-button` : 'confirm-ok-button'}
        >
          {okText}
        </Button>
      ]}
      data-testid={props['data-testid'] || 'confirm-modal'}
    >
      {content}
    </Modal>
  );
};

ConfirmModal.propTypes = {
  title: PropTypes.string,
  content: PropTypes.node,
  okText: PropTypes.string,
  cancelText: PropTypes.string,
  onOk: PropTypes.func,
  onCancel: PropTypes.func,
  okButtonProps: PropTypes.object,
  danger: PropTypes.bool,
  open: PropTypes.bool.isRequired,
  'data-testid': PropTypes.string,
};

export default ConfirmModal;
