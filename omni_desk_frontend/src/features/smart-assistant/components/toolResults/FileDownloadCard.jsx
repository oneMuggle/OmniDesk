import { useState } from 'react';
import { Card, Space, Button, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import { downloadOfficeFile } from '../../api/smartAssistantApi';

/**
 * Office 文件下载卡片 — 后端 office_generate 工具会返回
 * tool_result.file_download = { filename, download_url }。
 * download_url 末段是 token,点击下载按钮 → 调 downloadOfficeFile(token)
 * 拿 blob → createObjectURL 触发浏览器下载。
 */
function FileDownloadCard({ fileDownload }) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = (fileDownload.download_url || '').split('/').filter(Boolean).pop();
      const blob = await downloadOfficeFile(token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileDownload.filename || 'document.docx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      message.error(err.message || '下载失败');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <Space>
        <span>{fileDownload.filename}</span>
        <Button icon={<DownloadOutlined />} size="small" onClick={handleDownload} loading={downloading}>
          下载
        </Button>
      </Space>
    </Card>
  );
}

FileDownloadCard.propTypes = {
  fileDownload: PropTypes.shape({
    filename: PropTypes.string,
    download_url: PropTypes.string,
  }).isRequired,
};

export default FileDownloadCard;
