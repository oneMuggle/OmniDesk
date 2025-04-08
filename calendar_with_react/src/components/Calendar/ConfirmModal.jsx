import React, { useState } from 'react';
import { Modal, Button } from 'antd';

const ConfirmModal = ({
  title = '确认操作',
  content = '确定要执行此操作吗？',
  okText = '确定',
  cancelText = '取消',
  onOk,
  onCancel,
  okButtonProps = {},
  danger = false,
  children
}) => {
  const [visible, setVisible] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const showModal = () => {
    setVisible(true);
  };

  const handleOk = async () => {
    setConfirmLoading(true);
    try {
      await onOk?.();
      setVisible(false);
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancel = () => {
    onCancel?.();
    setVisible(false);
  };

  return (
    <>
      {React.cloneElement(React.Children.only(children), {
        onClick: (e) => {
          e.preventDefault();
          e.stopPropagation();
          showModal();
        }
      })}
      <Modal
        title={title}
        open={visible}
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
          >
            {okText}
          </Button>
        ]}
      >
        {content}
      </Modal>
    </>
  );
};

export default ConfirmModal;
