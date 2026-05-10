import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Select, DatePicker, Card, Row, Col, Space, Spin } from 'antd';
import { PlusOutlined, MinusCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import moment from 'moment';
import { getPersonnelDetails, updatePersonnel, getAllPositions } from '../api/personnelApi';
import {
import { logger } from '../../../shared/utils/logger';
    ProfessionalQualificationTable,
    PublicHousingInfoTable,
    BankAccountTable,
    FamilyMemberTable
} from '../components';

const { Option } = Select;

const PersonnelEditPage = ({ form: providedForm }) => {
    const { personnelId } = useParams();
    const [internalForm] = Form.useForm();
    const form = providedForm || internalForm;
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [positions, setPositions] = useState([]);
    const [error, setError] = useState(null);
    const [initialData, setInitialData] = useState(null);

    useEffect(() => {
        const fetchDetailsAndPositions = async () => {
            try {
                setLoading(true);
                const [detailsResponse, positionsResponse] = await Promise.all([
                    getPersonnelDetails(personnelId),
                    getAllPositions()
                ]);
                setPositions(positionsResponse || []);
                setInitialData(detailsResponse);
            } catch (error) {
                logger.error("获取人员详情失败:", error);
                setError('获取页面数据失败');
                message.error('获取页面数据失败');
            } finally {
                setLoading(false);
            }
        };
        fetchDetailsAndPositions();
    }, [personnelId]);

    useEffect(() => {
        if (initialData) {
            console.log('Setting form fields with:', JSON.stringify(initialData));
            form.setFieldsValue({
                ...initialData,
                position: initialData.position ? initialData.position.id : null,
                date_of_birth: initialData.date_of_birth ? moment(initialData.date_of_birth) : null,
                hire_date: initialData.hire_date ? moment(initialData.hire_date) : null,
                contracts: initialData.contracts?.map(c => ({ ...c, start_date: moment(c.start_date), end_date: moment(c.end_date) })) || [],
                educations: initialData.educations?.map(e => ({ ...e, start_date: moment(e.start_date), end_date: moment(e.end_date) })) || [],
                work_experiences: initialData.work_experiences?.map(w => ({ ...w, start_date: moment(w.start_date), end_date: moment(w.end_date) })) || [],
                professional_qualifications: initialData.professional_qualifications || [],
                public_housing_info: initialData.public_housing_info || [],
                bank_accounts: initialData.bank_accounts || [],
            });
            console.log('Form values after set:', JSON.stringify(form.getFieldsValue()));
        }
    }, [initialData, form]);

    const handleSubmit = async (values) => {
        try {
            setSaving(true);
            const {
                ...payload
            } = values;

            const dataToSend = {
                ...payload,
                date_of_birth: values.date_of_birth ? values.date_of_birth.format('YYYY-MM-DD') : null,
                hire_date: values.hire_date ? values.hire_date.format('YYYY-MM-DD') : null,
                contracts: values.contracts?.map(c => ({
                    ...c,
                    start_date: c.start_date ? c.start_date.format('YYYY-MM-DD') : null,
                    end_date: c.end_date ? c.end_date.format('YYYY-MM-DD') : null,
                })) || [],
            };

           if (dataToSend.id_card_number === '') {
               delete dataToSend.id_card_number;
           }
            await updatePersonnel(personnelId, dataToSend);
            message.success('更新成功');
            navigate('/control-panel/personnel');
        } catch (error) {
            logger.error('操作失败:', error);
            message.error('操作失败');
        } finally {
            setSaving(false);
        }
    };

    const renderDynamicList = (name, singular, fields) => (
        <Form.List name={name}>
            {(formFields, { add, remove }) => (
                <Card title={`${singular}信息`} className="mb-4" role="region" aria-label={`${singular}信息`}>
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
        return <div className="flex justify-center items-center h-screen" role="status"><Spin size="large" /></div>;
    }

    if (error) {
        return <div className="flex justify-center items-center h-screen">{error}</div>;
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
                <Form data-testid="personnel-edit-form" form={form} layout="vertical" onFinish={handleSubmit}>
                    <Row gutter={16}>
                        <Col span={8}><Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input /></Form.Item></Col>
                        <Col span={8}><Form.Item label="身份证号" name="id_card_number"><Input /></Form.Item></Col>
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
                        <ProfessionalQualificationTable isEditing={true} personnelId={parseInt(personnelId, 10)} />
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
                    <FamilyMemberTable personnelId={parseInt(personnelId, 10)} isEditing={true} />

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

PersonnelEditPage.propTypes = {
    form: PropTypes.object,
};

export default PersonnelEditPage;