#!/usr/bin/env python
"""
Test script to verify multi-format request handling for workspace creation.
This tests both the organization constraint fix and content-type parsing resolution.
"""
import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

import json
import uuid
from io import BytesIO
from PIL import Image
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.organizations.models import Organization, OrganizationMembership
from apps.workspaces.models import Workspace
from apps.workspaces.viewsets import WorkspaceViewSet

User = get_user_model()


class MultiFormatWorkspaceTest(TestCase):
    """Test workspace creation with both JSON and multipart requests."""
    
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test organization
        self.organization = Organization.objects.create(
            name='Test Organization',
            slug='test-org',
            owner=self.user
        )
        
        # Create organization membership
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role='owner',
            status='active',
            is_active=True
        )
        
        # Setup API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.workspace_data = {
            'organization': str(self.organization.id),
            'name': 'Test Workspace',
            'slug': 'test-workspace',
            'description': 'A test workspace',
            'workspace_type': 'development',
            'visibility': 'private'
        }
    
    def create_test_image(self):
        """Create a small test image file."""
        image = Image.new('RGB', (100, 100), color='red')
        image_file = BytesIO()
        image.save(image_file, 'JPEG')
        image_file.seek(0)
        image_file.name = 'test_image.jpg'
        return image_file
    
    def test_json_workspace_creation(self):
        """Test workspace creation with JSON payload (original working case)."""
        print("Testing JSON workspace creation...")
        
        response = self.client.post(
            '/api/v1/workspaces/',
            data=json.dumps(self.workspace_data),
            content_type='application/json'
        )
        
        print(f"JSON Response status: {response.status_code}")
        if response.status_code != status.HTTP_201_CREATED:
            print(f"JSON Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('organization_details', response.data)
        self.assertEqual(response.data['name'], 'Test Workspace')
    
    def test_multipart_workspace_creation_without_files(self):
        """Test workspace creation with multipart but no files."""
        print("Testing multipart workspace creation without files...")
        
        response = self.client.post(
            '/api/v1/workspaces/',
            data=self.workspace_data,
            format='multipart'
        )
        
        print(f"Multipart (no files) Response status: {response.status_code}")
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Multipart (no files) Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('organization_details', response.data)
        self.assertEqual(response.data['name'], 'Test Workspace')
    
    def test_multipart_workspace_creation_with_image(self):
        """Test workspace creation with multipart including image file."""
        print("Testing multipart workspace creation with image...")
        
        # Create test image
        test_image = self.create_test_image()
        
        # Prepare multipart data with file
        data = self.workspace_data.copy()
        data['name'] = 'Test Workspace with Image'
        data['slug'] = 'test-workspace-image'
        
        response = self.client.post(
            '/api/v1/workspaces/',
            data=data,
            files={'cover_image': test_image},
            format='multipart'
        )
        
        print(f"Multipart (with image) Response status: {response.status_code}")
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Multipart (with image) Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('organization_details', response.data)
        self.assertEqual(response.data['name'], 'Test Workspace with Image')
        
        # Verify workspace was created with proper organization relationship
        workspace = Workspace.objects.get(id=response.data['id'])
        self.assertEqual(workspace.organization.id, self.organization.id)
    
    def test_invalid_organization_id(self):
        """Test proper error handling for invalid organization ID."""
        print("Testing invalid organization ID handling...")
        
        invalid_data = self.workspace_data.copy()
        invalid_data['organization'] = str(uuid.uuid4())  # Non-existent organization
        
        response = self.client.post(
            '/api/v1/workspaces/',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        print(f"Invalid org Response status: {response.status_code}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('organization', response.data)


def run_tests():
    """Run the multi-format workspace creation tests."""
    print("="*60)
    print("MULTI-FORMAT WORKSPACE CREATION TESTS")
    print("="*60)
    
    # Import Django test framework
    from django.test.utils import get_runner
    from django.conf import settings
    
    test_runner = get_runner(settings)()
    
    # Run the test cases
    failures = test_runner.run_tests(['__main__.MultiFormatWorkspaceTest'])
    
    if failures:
        print(f"\n❌ {failures} test(s) failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed! Multi-format request handling is working correctly.")


if __name__ == '__main__':
    run_tests()
