import { useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Form,
  Input,
  Select,
  DatePicker,
  Button,
  Card,
  Space,
  message,
  Skeleton,
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import {
  getStudent,
  createStudent,
  updateStudent,
  listPersonnelPool,
} from '../../api/students';

const { Option } = Select;

export default function StudentEditPage() {
  const { id } = useParams();
  const isEdit = Boolean(id) && id !== 'new';
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: detail, isLoading } = useQuery({
    queryKey: ['joint-students', 'detail', id],
    queryFn: () => getStudent(id),
    enabled: isEdit,
  });

  const { data: poolData } = useQuery({
    queryKey: ['joint-students', 'personnel-pool'],
    queryFn: () => listPersonnelPool(),
  });

  const personnelPool = useMemo(() => poolData?.data || [], [poolData]);

  useEffect(() => {
    if (detail?.data) {
      form.setFieldsValue({
        ...detail.data,
        enrollment_date: detail.data.enrollment_date ? dayjs(detail.data.enrollment_date) : null,
        graduation_date: detail.data.graduation_date ? dayjs(detail.data.graduation_date) : null,
      });
    }
  }, [detail, form]);

  const saveMutation = useMutation({
    mutationFn: (values) => {
      const payload = {
        ...values,
        enrollment_date: values.enrollment_date?.format('YYYY-MM-DD'),
        graduation_date: values.graduation_date?.format('YYYY-MM-DD'),
      };
      if (isEdit) return updateStudent(id, payload);
      return createStudent(payload);
    },
    onSuccess: () => {
      message.success(isEdit ? '更新成功' : '创建成功');
      queryClient.invalidateQueries({ queryKey: ['joint-students', 'list'] });
      navigate('/joint-students/admin/students');
    },
    onError: () => {
      message.error('保存失败');
    },
  });

  const onFinish = (values) => {
    saveMutation.mutate(values);
  };

  if (isEdit && isLoading) {
    return <Skeleton active style={{ padding: 24 }} />;
  }

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>{isEdit ? '编辑联培生' : '新增联培生'}</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="所属人员"
            name="personnel"
            rules={[{ required: true, message: '请选择关联人员' }]}
          >
            <Select
              placeholder="选择 Personnel"
              showSearch
              optionFilterProp="label"
              disabled={isEdit}
            >
              {personnelPool.map((p) => (
                <Option key={p.id} value={p.id} label={p.name} disabled={p.has_joint_student}>
                  {p.name} {p.has_joint_student ? '（已关联）' : ''}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="学号"
            name="student_id"
            rules={[{ required: true, message: '请输入学号' }]}
          >
            <Input placeholder="例如 2026001" />
          </Form.Item>

          <Form.Item
            label="联培生类型"
            name="student_type"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select placeholder="选择类型">
              <Option value="master">硕士</Option>
              <Option value="phd">博士</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="入学日期"
            name="enrollment_date"
            rules={[{ required: true, message: '请选择入学日期' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="毕业日期" name="graduation_date">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="导师" name="mentor">
            <Select
              placeholder="选择导师"
              allowClear
              showSearch
              optionFilterProp="label"
            >
              {personnelPool.map((p) => (
                <Option key={p.id} value={p.id} label={p.name}>
                  {p.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={saveMutation.isPending}
              >
                保存
              </Button>
              <Button onClick={() => navigate('/joint-students/admin/students')}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
