from django.test import TestCase
from django.db.utils import IntegrityError
from .models import Personnel, Position, Contract, Education, WorkExperience
import datetime

class PersonnelModelTest(TestCase):

    def setUp(self):
        self.position = Position.objects.create(name="Developer")
        self.personnel = Personnel.objects.create(
            name="Test User",
            id_card_number="123456789012345678",
            position="Developer",
            department="IT",
        )

    def test_personnel_creation(self):
        """Test the creation of a Personnel instance."""
        self.assertEqual(self.personnel.name, "Test User")
        self.assertEqual(self.personnel.position, "Developer")
        self.assertEqual(Personnel.objects.count(), 1)

    def test_id_card_uniqueness(self):
        """Test that id_card_number must be unique."""
        with self.assertRaises(IntegrityError):
            Personnel.objects.create(
                name="Another User",
                id_card_number="123456789012345678", # Same as setUp
                position="QA",
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

    def test_cascade_delete(self):
        """Test that related objects are deleted when a personnel is deleted."""
        Contract.objects.create(personnel=self.personnel, contract_number="C1", start_date="2025-01-01", end_date="2026-01-01", contract_type="fixed-term")
        Education.objects.create(personnel=self.personnel, school="U", degree="B", major="CS", start_date="2020-01-01", end_date="2024-01-01")
        
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(Education.objects.count(), 1)
        
        self.personnel.delete()
        
        self.assertEqual(Personnel.objects.count(), 0)
        self.assertEqual(Contract.objects.count(), 0)
        self.assertEqual(Education.objects.count(), 0)
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class PersonnelAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword', role='admin')

        self.personnel_data = {
            "name": "API Test User",
            "id_card_number": "987654321098765432",
            "position": "API Tester",
            "department": "QA"
        }
        self.personnel = Personnel.objects.create(**self.personnel_data)

    def test_list_personnel(self):
        """Test listing all personnel."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/personnel/personnel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_personnel(self):
        """Test creating a new personnel."""
        self.client.force_authenticate(user=self.user)
        data = {
            "name": "New API User",
            "id_card_number": "112233445566778899",
            "position": "Newbie",
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
        self.admin_user = User.objects.create_user(username='adminuser', password='password', role='admin')
        self.regular_user = User.objects.create_user(username='regularuser', password='password', role='user')
        self.personnel = Personnel.objects.create(name="Permissions Test", id_card_number="111222333444555666")

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access the API."""
        response = self.client.get('/api/personnel/personnel/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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