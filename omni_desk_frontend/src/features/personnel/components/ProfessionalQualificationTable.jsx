import PropTypes from 'prop-types';
import { getQualifications, createQualification, updateQualification, deleteQualification } from '../api/personnelApi';
import CrudSubTable from './CrudSubTable';

// 职业资质子表：薄封装，复用泛型 CrudSubTable
const QUALIFICATION_COLUMNS = [
  { title: '证书名称', dataIndex: 'name', key: 'name' },
  { title: '颁发机构', dataIndex: 'issuing_authority', key: 'issuing_authority' },
  { title: '颁发日期', dataIndex: 'issue_date', key: 'issue_date' },
];

const QUALIFICATION_FORM_FIELDS = [
  { name: 'name', label: '证书名称' },
  { name: 'issuing_authority', label: '颁发机构' },
  { name: 'issue_date', label: '颁发日期', inputType: 'date' },
];

const ProfessionalQualificationTable = ({ personnelId }) => (
  <CrudSubTable
    title="职业资质"
    fetchApi={getQualifications}
    createApi={createQualification}
    updateApi={updateQualification}
    deleteApi={deleteQualification}
    columns={QUALIFICATION_COLUMNS}
    formFields={QUALIFICATION_FORM_FIELDS}
    personnelId={personnelId}
  />
);

ProfessionalQualificationTable.propTypes = {
  personnelId: PropTypes.number.isRequired,
};

export default ProfessionalQualificationTable;
