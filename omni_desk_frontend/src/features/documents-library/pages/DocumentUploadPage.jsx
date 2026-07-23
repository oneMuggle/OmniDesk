/**
 * 文档上传页 (paperless-ngx 集成)
 *
 * 使用 AntD Upload.Dragger + Form 组合,
 * 上传到 `/api/paperless/upload/`,成功后跳转到文档库。
 */
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Form, Input, Select, Upload, Button, message, Card, Space, Alert,
} from 'antd';
import { InboxOutlined, UploadOutlined } from '@ant-design/icons';
import axiosInstance from '../../../shared/api/axiosConfig';
import PaperlessHealthBanner from '../components/PaperlessHealthBanner';

const { Dragger } = Upload;
const { TextArea } = Input;

const SOURCE_TYPE_OPTIONS = [
  { value: 'project_document', label: '项目文档' },
  { value: 'contract', label: '合同' },
  { value: 'policy', label: '制度文件' },
  { value: 'compliance_report', label: '合规报告' },
  { value: 'personnel_file', label: '人事档案' },
];

const uploadDocument = async (values) => {
  const formData = new FormData();
  formData.append('file', values.file.file);
  formData.append('title', values.title || '');
  formData.append('source_type', values.source_type || '');
  if (values.description) formData.append('description', values.description);

  const { data } = await axiosInstance.post('/paperless/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export default function DocumentUploadPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [fileList, setFileList] = useState([]);

  const mutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      message.success('上传成功,文档将在后台同步到 paperless');
      form.resetFields();
      setFileList([]);
      navigate('/documents-library');
    },
    onError: (error) => {
      const msg = error.response?.data?.detail
        || error.response?.data?.message
        || error.message
        || '上传失败';
      message.error(msg);
    },
  });

  const handleSubmit = (values) => {
    if (!values.file) {
      message.warning('请先选择文件');
      return;
    }
    mutation.submit(values);
  };

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>上传文档</h2>

      <PaperlessHealthBanner />

      <Alert
        type="info"
        showIcon
        message="上传说明"
        description="文档将先存入 OmniDesk,后台自动同步到 paperless 文档库。同步过程可能需要几分钟。"
        style={{ marginBottom: 16 }}
      />

      <Card style={{ maxWidth: 720 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            label="文件"
            name="file"
            rules={[{ required: true, message: '请上传文件' }]}
            valuePropName="file"
            getValueFromEvent={(e) => {
              if (Array.isArray(e)) return { file: e[0] };
              return e;
            }}
          >
            <Dragger
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: newList }) => setFileList(newList.slice(-1))}
              onRemove={() => setFileList([])}
              maxCount={1}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域</p>
              <p className="ant-upload-hint">支持 PDF、Office、图片等常见文档格式</p>
            </Dragger>
          </Form.Item>

          <Form.Item
            label="标题"
            name="title"
            rules={[{ max: 200, message: '标题最多 200 字' }]}
          >
            <Input placeholder="文档标题(可选,默认使用文件名)" />
          </Form.Item>

          <Form.Item label="来源类型" name="source_type">
            <Select
              placeholder="选择来源(可选)"
              options={SOURCE_TYPE_OPTIONS}
              allowClear
            />
          </Form.Item>

          <Form.Item label="说明" name="description">
            <TextArea rows={3} placeholder="文档说明(可选)" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                icon={<UploadOutlined />}
                loading={mutation.isPending}
              >
                上传
              </Button>
              <Button onClick={() => navigate('/documents-library')}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
