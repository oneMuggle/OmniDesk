import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Select, DatePicker, Card, Row, Col, Space, Spin } from 'antd';
import { PlusOutlined, MinusCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import moment from 'moment';
import { getPersonnelDetails, updatePersonnel, getAllPositions } from '../api/personnelApi';
import {
    ProfessionalQualificationTable,
    PublicHousingInfoTable,
    BankAccountTable,
    FamilyMemberTable
} from '../components';

const { Option } = Select;

const PersonnelEditPage = () => {
    const { id } = useParams();
    const [form] = Form.useForm();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [positions, setPositions] = useState([]);

    useEffect(() => {
        const fetchDetailsAndPositions = async () => {
            try {
                setLoading(true);
                const [detailsResponse, positionsResponse] = await Promise.all([
                    getPersonnelDetails(id),
                    getAllPositions()
                ]);
                
                const record = detailsResponse;
                setPositions(positionsResponse || []);

                form.setFieldsValue({
                    ...record,
                    position: record.position ? record.position.id : null,
                    date_of_birth: record.date_of_birth ? moment(record.date_of_birth) : null,
                    hire_date: record.hire_date ? moment(record.hire_date) : null,
                    contracts: record.contracts?.map(c => ({ ...c, start_date: moment(c.start_date), end_date: moment(c.end_date) })) || [],
                    educations: record.educations?.map(e => ({ ...e, start_date: moment(e.start_date), end_date: moment(e.end_date) })) || [],
                    work_experiences: record.work_experiences?.map(w => ({ ...w, start_date: moment(w.start_date), end_date: moment(w.end_date) })) || [],
                    professional_qualifications: record.professional_qualifications || [],
                    public_housing_info: record.public_housing_info || [],
                    bank_accounts: record.bank_accounts || [],
                });
            } catch (error) {
                message.error('获取页面数据失败');
            } finally {
                setLoading(false);
            }
        };
        fetchDetailsAndPositions();
    }, [id, form]);

    const handleSubmit = async () => {
        try {
            setSaving(true);
            const values = await form.validateFields();
            const dataToSend = {
                ...values,
                date_of_birth: values.date_of_birth?.format('YYYY-MM-DD'),
                hire_date: values.hire_date?.format('YYYY-MM-DD'),
                contracts: values.contracts?.map(c => ({ ...c, start_date: c.start_date.format('YYYY-MM-DD'), end_date: c.end_date.format('YYYY-MM-DD') })),
                educations: values.educations?.map(e => ({ ...e, start_date: e.start_date.format('YYYY-MM-DD'), end_date: e.end_date.format('YYYY-MM-DD') })),
                work_experiences: values.work_experiences?.map(w => ({ ...w, start_date: w.start_date.format('YYYY-MM-DD'), end_date: w.end_date.format('YYYY-MM-DD') })),
                professional_qualifications: values.professional_qualifications,
                public_housing_info: values.public_housing_info,
                bank_accounts: values.bank_accounts,
            };
            await updatePersonnel(id, dataToSend);
            message.success('更新成功');
            navigate('/control-panel/personnel');
        } catch (error) {
            console.error('操作失败:', error);
            message.error('操作失败');
        } finally {
            setSaving(false);
        }
    };

    const renderDynamicList = (name, singular, fields) => (
        <Form.List name={name}>
            {(formFields, { add, remove }) => (
                <Card title={`${singular}信息`} className="mb-4">
                    {formFields.map(({ key, name: fieldName, ...restField }) => (
                        <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                            {fields.map(field => (
                                <Form.Item key={field.name} {...restField} name={[fieldName, field.name]} rules={field.rules}>
                                    {field.type === 'date' ? <DatePicker placeholder={field.placeholder} style={{ width: '100%' }} /> : <Input placeholder={field.placeholder} />}
                                </Form.Item>
                            ))}
                            <MinusCircleOutlined onClick={() => remove(fieldName)} />
                        </Space>
                    ))}
                    <Form.Item>
                        <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                            添加{singular}
                        </Button>
                    </Form.Item>
                </Card>
            )}
        </Form.List>
    );

    if (loading) {
        return <div className="flex justify-center items-center h-screen"><Spin size="large" /></div>;
    }

    return (
        <div className="p-8 bg-gray-100 min-h-screen">
            <Card>
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold">编辑人员详细信息</h1>
                    <Link to="/control-panel/personnel">
                        <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
                    </Link>
                </div>
                <Form form={form} layout="vertical" onFinish={handleSubmit}>
                    <Row gutter={16}>
                        <Col span={8}><Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input /></Form.Item></Col>
                        <Col span={8}><Form.Item label="身份证号" name="id_card_number" rules={[{ required: true }]}><Input /></Form.Item></Col>
                        <Col span={8}><Form.Item label="出生年月" name="date_of_birth"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
                        <Col span={8}><Form.Item label="联系电话" name="phone_number"><Input /></Form.Item></Col>
                        <Col span={16}><Form.Item label="家庭住址" name="address"><Input /></Form.Item></Col>
                        <Col span={8}><Form.Item label="部门" name="department"><Input /></Form.Item></Col>
                        <Col span={8}>
                            <Form.Item label="职位" name="position">
                                <Select placeholder="请选择职位">
                                    {positions.map(pos => (
                                        <Option key={pos.id} value={pos.id}>{pos.name}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        </Col>
                        <Col span={8}><Form.Item label="入职日期" name="hire_date"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
                        <Col span={8}><Form.Item label="员工状态" name="status" initialValue="active">
                            <Select>
                                <Option value="active">在职</Option>
                                <Option value="inactive">离职</Option>
                            </Select>
                        </Form.Item></Col>
                    </Row>
                    {renderDynamicList('contracts', '合同', [
                        { name: 'contract_number', placeholder: '合同编号', rules: [{ required: true }] },
                        { name: 'contract_type', placeholder: '合同类型' },
                        { name: 'start_date', placeholder: '开始日期', type: 'date', rules: [{ required: true }] },
                        { name: 'end_date', placeholder: '结束日期', type: 'date', rules: [{ required: true }] },
                    ])}
                    {renderDynamicList('educations', '教育背景', [
                        { name: 'school', placeholder: '毕业院校', rules: [{ required: true }] },
                        { name: 'degree', placeholder: '学历' },
                        { name: 'major', placeholder: '专业' },
                        { name: 'start_date', placeholder: '开始日期', type: 'date' },
                        { name: 'end_date', placeholder: '结束日期', type: 'date' },
                    ])}
                    {renderDynamicList('work_experiences', '工作经历', [
                        { name: 'company', placeholder: '公司名称', rules: [{ required: true }] },
                        { name: 'position', placeholder: '职位' },
                        { name: 'start_date', placeholder: '开始日期', type: 'date' },
                        { name: 'end_date', placeholder: '结束日期', type: 'date' },
                        { name: 'description', placeholder: '工作描述' },
                    ])}

                    <h2 className="text-xl font-semibold mt-8 mb-4">职业资质</h2>
                    <Form.Item name="professional_qualifications">
                        <ProfessionalQualificationTable isEditing={true} />
                    </Form.Item>

                    <h2 className="text-xl font-semibold mt-8 mb-4">公积金信息</h2>
                    <Form.Item name="public_housing_info">
                        <PublicHousingInfoTable isEditing={true} />
                    </Form.Item>

                    <h2 className="text-xl font-semibold mt-8 mb-4">银行账户</h2>
                    <Form.Item name="bank_accounts">
                        <BankAccountTable isEditing={true} />
                    </Form.Item>

                    <h2 className="text-xl font-semibold mt-8 mb-4">家庭成员</h2>
                    <FamilyMemberTable personnelId={parseInt(id, 10)} isEditing={true} />

                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={saving}>
                            保存更改
                        </Button>
                    </Form.Item>
                </Form>
            </Card>
        </div>
    );
};

export default PersonnelEditPage;