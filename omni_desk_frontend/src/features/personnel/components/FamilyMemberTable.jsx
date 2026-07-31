import PropTypes from 'prop-types';
import { getFamilyMembers, createFamilyMember, updateFamilyMember, deleteFamilyMember } from '../api/personnelApi';
import CrudSubTable from './CrudSubTable';

// 家庭成员子表：薄封装，复用泛型 CrudSubTable
const FAMILY_MEMBER_COLUMNS = [
  { title: '姓名', dataIndex: 'name', key: 'name' },
  { title: '关系', dataIndex: 'relationship', key: 'relationship' },
  { title: '联系电话', dataIndex: 'contact_number', key: 'contact_number' },
];

const FAMILY_MEMBER_FORM_FIELDS = [
  { name: 'name', label: '姓名' },
  { name: 'relationship', label: '关系' },
  { name: 'contact_number', label: '联系电话' },
];

const FamilyMemberTable = ({ personnelId }) => (
  <CrudSubTable
    title="家庭成员"
    fetchApi={getFamilyMembers}
    createApi={createFamilyMember}
    updateApi={updateFamilyMember}
    deleteApi={deleteFamilyMember}
    columns={FAMILY_MEMBER_COLUMNS}
    formFields={FAMILY_MEMBER_FORM_FIELDS}
    personnelId={personnelId}
  />
);

FamilyMemberTable.propTypes = {
  personnelId: PropTypes.number.isRequired,
};

export default FamilyMemberTable;
