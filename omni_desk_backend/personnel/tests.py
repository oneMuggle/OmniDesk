from django.test import TestCase
from django.db.utils import IntegrityError
from personnel.models import Personnel, Position, Contract, Education, WorkExperience, ProfessionalQualification, FamilyMember
import datetime

class PersonnelModelTest(TestCase):

    def setUp(self):
        self.position = Position.objects.create(name="Developer")
        self.personnel = Personnel.objects.create(
            name="Test User",
            id_card_number="123456789012345678",
            position=self.position,
            department="IT",
        )

    def test_personnel_creation(self):
        """Test the creation of a Personnel instance."""
        self.assertEqual(self.personnel.name, "Test User")
        self.assertEqual(self.personnel.position.name, "Developer")
        self.assertEqual(Personnel.objects.count(), 1)

    def test_id_card_uniqueness(self):
        """Test that id_card_number must be unique."""
        with self.assertRaises(IntegrityError):
            Personnel.objects.create(
                name="Another User",
                id_card_number="123456789012345678", # Same as setUp
                position=self.position,
                department="IT",
            )

    def test_contract_creation(self):
        """Test creating a contract related to a personnel."""
        contract = Contract.objects.create(
            personnel=self.personnel,
            contract_number="C-2025-01",
            contract_type="permanent",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2028, 1, 1),
        )
        self.assertEqual(self.personnel.contracts.count(), 1)
        self.assertEqual(contract.contract_number, "C-2025-01")

    def test_education_creation(self):
        """Test creating an education record related to a personnel."""
        education = Education.objects.create(
            personnel=self.personnel,
            school="Test University",
            degree="Bachelor",
            major="Computer Science",
            start_date=datetime.date(2020, 9, 1),
            end_date=datetime.date(2024, 7, 1),
        )
        self.assertEqual(self.personnel.educations.count(), 1)
        self.assertEqual(education.school, "Test University")

    def test_work_experience_creation(self):
        """Test creating a work experience record related to a personnel."""
        work_experience = WorkExperience.objects.create(
            personnel=self.personnel,
            company="Test Corp",
            position="Junior Developer",
            start_date=datetime.date(2024, 8, 1),
            end_date=datetime.date(2025, 8, 1),
        )
        self.assertEqual(self.personnel.work_experiences.count(), 1)
        self.assertEqual(work_experience.company, "Test Corp")

    def test_professional_qualification_creation(self):
        """Test creating a professional qualification record."""
        qualification = ProfessionalQualification.objects.create(
            personnel=self.personnel,
            qualification_name="Certified Tester",
            issue_date=datetime.date(2025, 1, 1),
        )
        self.assertEqual(self.personnel.qualifications.count(), 1)
        self.assertEqual(qualification.qualification_name, "Certified Tester")

    def test_family_member_creation(self):
        """Test creating a family member record."""
        family_member = FamilyMember.objects.create(
            personnel=self.personnel,
            name="Jane Doe",
            relationship="Spouse",
        )
        self.assertEqual(self.personnel.family_members.count(), 1)
        self.assertEqual(family_member.name, "Jane Doe")

    def test_cascade_delete(self):
        """Test that related objects are deleted when a personnel is deleted."""
        Contract.objects.create(personnel=self.personnel, contract_number="C1", start_date="2025-01-01", end_date="2026-01-01", contract_type="fixed-term")
        Education.objects.create(personnel=self.personnel, school="U", degree="B", major="CS", start_date="2020-01-01", end_date="2024-01-01")
        ProfessionalQualification.objects.create(personnel=self.personnel, qualification_name="Cert1", issue_date="2025-01-01")
        FamilyMember.objects.create(personnel=self.personnel, name="Spouse", relationship="Spouse")
        
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(Education.objects.count(), 1)
        self.assertEqual(ProfessionalQualification.objects.count(), 1)
        self.assertEqual(FamilyMember.objects.count(), 1)
        
        self.personnel.delete()
        
        self.assertEqual(Personnel.objects.count(), 0)
        self.assertEqual(Contract.objects.count(), 0)
        self.assertEqual(Education.objects.count(), 0)
        self.assertEqual(ProfessionalQualification.objects.count(), 0)
        self.assertEqual(FamilyMember.objects.count(), 0)
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

class PersonnelAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.user.groups.add(admin_group)

        position_obj = Position.objects.create(name="API Tester")
        self.personnel_data = {
            "name": "API Test User",
            "id_card_number": "987654321098765432",
            "position": position_obj.id,
            "department": "QA"
        }
        self.personnel = Personnel.objects.create(
            name="API Test User",
            id_card_number="987654321098765432",
            position=position_obj,
            department="QA"
        )

    def test_list_personnel(self):
        """Test listing all personnel."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/personnel/personnel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_personnel(self):
        """Test creating a new personnel."""
        self.client.force_authenticate(user=self.user)
        new_position = Position.objects.create(name="Newbie")
        data = {
            "name": "New API User",
            "id_card_number": "112233445566778899",
            "position": new_position.id,
            "department": "Training"
        }
        response = self.client.post('/api/personnel/personnel/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Personnel.objects.count(), 2)

    def test_retrieve_personnel(self):
        """Test retrieving a single personnel's details."""
        self.client.force_authenticate(user=self.user)
        Contract.objects.create(personnel=self.personnel, contract_number="API-C1", start_date="2025-01-01", end_date="2026-01-01", contract_type="fixed-term")
        response = self.client.get(f'/api/personnel/personnel/{self.personnel.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.personnel.name)
        self.assertEqual(len(response.data['contracts']), 1)

    def test_update_personnel(self):
        """Test updating a personnel's information."""
        self.client.force_authenticate(user=self.user)
        update_data = {'name': 'Updated API User', 'department': 'Senior QA'}
        response = self.client.patch(f'/api/personnel/personnel/{self.personnel.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.personnel.refresh_from_db()
        self.assertEqual(self.personnel.name, 'Updated API User')
        self.assertEqual(self.personnel.department, 'Senior QA')

    def test_delete_personnel(self):
        """Test deleting a personnel."""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/personnel/personnel/{self.personnel.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Personnel.objects.count(), 0)

class PersonnelPermissionTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        user_group, _ = Group.objects.get_or_create(name='User')
        self.admin_user = User.objects.create_user(username='adminuser', password='password')
        self.admin_user.groups.add(admin_group)
        self.regular_user = User.objects.create_user(username='regularuser', password='password')
        self.regular_user.groups.add(user_group)
        self.personnel = Personnel.objects.create(name="Permissions Test", id_card_number="111222333444555666")

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access the API."""
        response = self.client.get('/api/personnel/personnel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_read_access(self):
        """Test that regular users have read-only access."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/personnel/personnel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_write_access_denied(self):
        """Test that regular users cannot create, update, or delete personnel."""
        self.client.force_authenticate(user=self.regular_user)
        
        # Test POST (Create)
        data = {"name": "Forbidden User", "id_card_number": "000"}
        response = self.client.post('/api/personnel/personnel/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test PUT (Update)
        update_data = {'name': 'Forbidden Update'}
        response = self.client.put(f'/api/personnel/personnel/{self.personnel.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test DELETE
        response = self.client.delete(f'/api/personnel/personnel/{self.personnel.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BaseAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.personnel = Personnel.objects.create(
            name="Test Personnel",
            id_card_number="111111111111111111"
        )

class ProfessionalQualificationAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.qualification_data = {
            'personnel': self.personnel.id,
            'qualification_name': 'Project Management Professional',
            'issue_date': '2025-01-15',
            'certificate_id': 'PMP12345'
        }
        self.qualification = ProfessionalQualification.objects.create(
            personnel=self.personnel,
            qualification_name='Existing Qualification',
            issue_date='2024-01-01'
        )
        self.url = '/api/personnel/qualifications/'

    def test_list_qualifications(self):
        """Test listing professional qualifications."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_qualification(self):
        """Test creating a professional qualification."""
        response = self.client.post(self.url, self.qualification_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProfessionalQualification.objects.count(), 2)

    def test_retrieve_qualification(self):
        """Test retrieving a single professional qualification."""
        url = f'{self.url}{self.qualification.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['qualification_name'], self.qualification.qualification_name)

    def test_update_qualification(self):
        """Test updating a professional qualification."""
        update_data = {'qualification_name': 'Updated Qualification Name'}
        url = f'{self.url}{self.qualification.id}/'
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.qualification.refresh_from_db()
        self.assertEqual(self.qualification.qualification_name, 'Updated Qualification Name')

    def test_delete_qualification(self):
        """Test deleting a professional qualification."""
        url = f'{self.url}{self.qualification.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ProfessionalQualification.objects.count(), 0)

    def test_unauthenticated_access_denied(self):
        """Test unauthenticated users cannot access the endpoint."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FamilyMemberAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.family_member_data = {
            'personnel': self.personnel.id,
            'name': 'John Doe',
            'relationship': 'Son',
            'contact_number': '1234567890'
        }
        self.family_member = FamilyMember.objects.create(
            personnel=self.personnel,
            name='Jane Doe',
            relationship='Daughter'
        )
        self.url = '/api/personnel/family-members/'

    def test_list_family_members(self):
        """Test listing family members."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_family_member(self):
        """Test creating a family member."""
        response = self.client.post(self.url, self.family_member_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FamilyMember.objects.count(), 2)

    def test_retrieve_family_member(self):
        """Test retrieving a single family member."""
        url = f'{self.url}{self.family_member.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.family_member.name)

    def test_update_family_member(self):
        """Test updating a family member."""
        update_data = {'name': 'Jane Doe Updated'}
        url = f'{self.url}{self.family_member.id}/'
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.family_member.refresh_from_db()
        self.assertEqual(self.family_member.name, 'Jane Doe Updated')

    def test_delete_family_member(self):
        """Test deleting a family member."""
        url = f'{self.url}{self.family_member.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(FamilyMember.objects.count(), 0)

    def test_unauthenticated_access_denied(self):
        """Test unauthenticated users cannot access the endpoint."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
class PersonnelViewSetTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        self.admin_user = User.objects.create_user(username='admin_test', password='password')
        self.admin_user.groups.add(admin_group)

    def test_list_personnel(self):
        """测试获取人员列表"""
        url = '/api/personnel/personnel/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_personnel(self):
        """测试创建人员"""
        self.client.force_authenticate(user=self.admin_user)
        url = '/api/personnel/personnel/'
        data = {'name': '新人', 'id_card_number': 'new_id_123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Personnel.objects.count(), 2)
        self.assertEqual(response.data['name'], '新人')

    def test_retrieve_personnel(self):
        """测试获取单个人员信息"""
        url = f'/api/personnel/personnel/{self.personnel.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.personnel.name)

    def test_update_personnel(self):
        """测试更新人员信息"""
        self.client.force_authenticate(user=self.admin_user)
        url = f'/api/personnel/personnel/{self.personnel.id}/'
        data = {'name': '张三更新', 'id_card_number': self.personnel.id_card_number}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.personnel.refresh_from_db()
        self.assertEqual(self.personnel.name, '张三更新')

    def test_delete_personnel(self):
        """测试删除人员"""
        self.client.force_authenticate(user=self.admin_user)
        url = f'/api/personnel/personnel/{self.personnel.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Personnel.objects.count(), 0)