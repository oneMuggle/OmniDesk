import React from 'react';
import { Upload, Button, Space, Typography } from 'antd';
import { PaperClipOutlined, CloseOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import { notifications } from '../utils/notifications';
import { validateFileSize } from '../utils/upload';

const ALLOWED_EXTENSIONS = ['.docx', '.pdf', '.xlsx', '.pptx', '.txt', '.md', '.csv'];

/**
 * 校验附件是否合法。导出为纯函数便于单测。
 * @returns {{ok: boolean, reason?: string}}
 */
export function validateFile({ name = '', size = 0 } = {}) {
  const idx = name.toLowerCase().lastIndexOf('.');
  const ext = idx >= 0 ? name.toLowerCase().slice(idx) : '';
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return { ok: false, reason: '仅支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv' };
  }
  const sizeCheck = validateFileSize({ name, size });
  if (!sizeCheck.ok) {
    return sizeCheck;
  }
  return { ok: true };
}

/**
 * 聊天附件选择器：白名单校验 + 缩略 chip + 移除。
 */
export default function FileAttachmentInput({ value = null, onChange, disabled = false }) {
  const handleBeforeUpload = (file) => {
    const result = validateFile(file);
    if (!result.ok) {
      notifications.showError(result.reason);
      return false;
    }
    onChange(file);
    return false; // 阻止自动上传，交给聊天发送流程
  };

  return (
    <Space size={4}>
      <Upload
        accept={ALLOWED_EXTENSIONS.join(',')}
        beforeUpload={handleBeforeUpload}
        showUploadList={false}
        disabled={disabled}
      >
        <Button icon={<PaperClipOutlined />} size="small" disabled={disabled}>
          选择文件
        </Button>
      </Upload>
      {value && (
        <Typography.Text type="secondary" style={{ maxWidth: 200 }} ellipsis>
          {value.name}
        </Typography.Text>
      )}
      {value && (
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={() => onChange(null)}
          aria-label="移除附件"
        />
      )}
    </Space>
  );
}

FileAttachmentInput.propTypes = {
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
