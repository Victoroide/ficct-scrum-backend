#!/usr/bin/env python
"""
Quick test script for Member Endpoint Fix.
Run: python test_member_endpoint.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.serializers import OrganizationMemberSerializer

def test_member_serialization():
    """Test that member serialization works without errors."""
    print("=" * 80)
    print("TESTING MEMBER ENDPOINT FIX")
    print("=" * 80)
    
    # Test 1: Check if organizations exist
    print("\n[Test 1] Checking organizations...")
    org_count = Organization.objects.count()
    print(f"✓ Found {org_count} organization(s)")
    
    if org_count == 0:
        print("⚠ No organizations found. Please create one first.")
        return False
    
    # Test 2: Check memberships
    print("\n[Test 2] Checking memberships...")
    membership_count = OrganizationMembership.objects.count()
    print(f"✓ Found {membership_count} membership(s)")
    
    if membership_count == 0:
        print("⚠ No memberships found. Please add members first.")
        return False
    
    # Test 3: Test serialization with query optimization
    print("\n[Test 3] Testing serialization with query optimization...")
    try:
        memberships = OrganizationMembership.objects.select_related(
            'user', 'organization', 'invited_by'
        ).prefetch_related('user__profile')[:5]  # Limit to 5 for testing
        
        serializer = OrganizationMemberSerializer(memberships, many=True)
        data = serializer.data
        
        print(f"✓ Successfully serialized {len(data)} membership(s)")
        
        # Test 4: Verify data structure
        print("\n[Test 4] Verifying data structure...")
        if data:
            first = data[0]
            required_fields = ['id', 'user', 'organization', 'role', 'role_display']
            
            for field in required_fields:
                if field not in first:
                    print(f"✗ Missing field: {field}")
                    return False
                print(f"  ✓ {field}: {type(first[field]).__name__}")
            
            # Verify user structure
            if first['user']:
                user_fields = ['id', 'username', 'email', 'full_name']
                print("\n  User fields:")
                for field in user_fields:
                    if field in first['user']:
                        print(f"    ✓ {field}: {first['user'][field]}")
                    else:
                        print(f"    ✗ Missing: {field}")
            
            # Verify organization structure
            if first['organization']:
                org_fields = ['id', 'name', 'slug']
                print("\n  Organization fields:")
                for field in org_fields:
                    if field in first['organization']:
                        print(f"    ✓ {field}: {first['organization'][field]}")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - Endpoint should work correctly")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n✗ Error during serialization: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 80)
        print("❌ TESTS FAILED")
        print("=" * 80)
        return False

if __name__ == '__main__':
    success = test_member_serialization()
    sys.exit(0 if success else 1)
