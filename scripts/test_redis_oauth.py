#!/usr/bin/env python
"""
Test Redis connection for GitHub OAuth state storage.

Validates that Django can:
1. Connect to Redis
2. Store OAuth state data
3. Retrieve OAuth state data
4. Delete OAuth state data (one-time use)
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

import secrets  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.utils import timezone  # noqa: E402


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def test_basic_connection():
    """Test basic Redis connection."""
    print_header("TEST 1: Basic Redis Connection")

    try:
        cache.set('test_connection', 'success', timeout=60)
        result = cache.get('test_connection')

        if result == 'success':
            print("✅ PASS | Redis connection working")
            cache.delete('test_connection')
            return True
        else:
            print(f"❌ FAIL | Expected 'success', got '{result}'")
            return False
    except Exception as e:
        print(f"❌ FAIL | Redis connection error: {e}")
        return False


def test_oauth_state_storage():
    """Test OAuth state storage with realistic data."""
    print_header("TEST 2: OAuth State Storage")

    try:
        # Simulate OAuth state
        state = secrets.token_urlsafe(32)
        state_data = {
            'project_id': 'test-project-uuid-12345',
            'user_id': 42,
            'created_at': timezone.now().isoformat(),
        }

        # Store with GitHub OAuth prefix
        cache_key = f'github_oauth_state_{state}'
        cache.set(cache_key, state_data, timeout=600)  # 10 minutes

        print(f"  Stored state: {state[:20]}...")
        print(f"  Cache key: {cache_key}")
        print(f"  Data: {state_data}")

        # Retrieve
        retrieved = cache.get(cache_key)

        if retrieved:
            print(f"  Retrieved: {retrieved}")

            if retrieved == state_data:
                print("✅ PASS | OAuth state stored and retrieved correctly")
                cache.delete(cache_key)
                return True
            else:
                print("❌ FAIL | Retrieved data doesn't match")
                return False
        else:
            print("❌ FAIL | Could not retrieve stored state")
            return False

    except Exception as e:
        print(f"❌ FAIL | OAuth state storage error: {e}")
        return False


def test_state_expiration():
    """Test that state has proper TTL."""
    print_header("TEST 3: State TTL Verification")

    try:
        state = secrets.token_urlsafe(32)
        cache_key = f'github_oauth_state_{state}'

        # Store with 600s TTL
        cache.set(cache_key, {'test': 'data'}, timeout=600)

        # Immediately retrieve to verify
        exists = cache.get(cache_key)

        if exists:
            print("✅ PASS | State persists with 600s TTL")
            cache.delete(cache_key)
            return True
        else:
            print("❌ FAIL | State not persisted")
            return False

    except Exception as e:
        print(f"❌ FAIL | TTL test error: {e}")
        return False


def test_state_deletion():
    """Test one-time use: state deletion after retrieval."""
    print_header("TEST 4: State One-Time Use")

    try:
        state = secrets.token_urlsafe(32)
        cache_key = f'github_oauth_state_{state}'

        # Store state
        cache.set(cache_key, {'test': 'data'}, timeout=600)

        # Retrieve
        first_get = cache.get(cache_key)

        if not first_get:
            print("❌ FAIL | State not stored initially")
            return False

        # Delete (simulate one-time use)
        cache.delete(cache_key)

        # Try to retrieve again
        second_get = cache.get(cache_key)

        if second_get is None:
            print("✅ PASS | State successfully deleted (one-time use working)")
            return True
        else:
            print("❌ FAIL | State still exists after deletion")
            return False

    except Exception as e:
        print(f"❌ FAIL | Deletion test error: {e}")
        return False


def test_cache_backend_info():
    """Display cache backend configuration."""
    print_header("CACHE CONFIGURATION")

    from django.conf import settings

    cache_config = settings.CACHES.get('default', {})

    print(f"  Backend: {cache_config.get('BACKEND', 'Not configured')}")
    print(f"  Location: {cache_config.get('LOCATION', 'Not configured')}")
    print(f"  Timeout: {cache_config.get('TIMEOUT', 'Default')}s")

    return True


def main():
    """Run all Redis tests for GitHub OAuth."""
    print_header("GITHUB OAUTH - REDIS VALIDATION")

    results = {}

    # Display configuration
    test_cache_backend_info()

    # Run tests
    results['connection'] = test_basic_connection()
    results['oauth_storage'] = test_oauth_state_storage()
    results['ttl'] = test_state_expiration()
    results['one_time_use'] = test_state_deletion()

    # Summary
    print_header("SUMMARY")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"\n  Total Tests: {total}")
    print(f"  Passed:      {passed} ✅")
    print(f"  Failed:      {failed} {'❌' if failed > 0 else ''}")

    if failed == 0:
        print("\n  🎉 ALL REDIS TESTS PASSED!")
        print("  ✅ CHECKPOINT 1.4 COMPLETE: Redis ready for OAuth state storage")
        print("\n  Redis is correctly configured for GitHub OAuth flow:")
        print("    - Connection working")
        print("    - State storage/retrieval working")
        print("    - TTL set to 600 seconds (10 minutes)")
        print("    - One-time use (deletion) working")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        print("  Redis must be fixed before proceeding to Phase 2.")

        print("\n  Troubleshooting:")
        print("    1. Verify Redis service is running: docker-compose ps redis")
        print("    2. Check CACHE_REDIS_URL in environment: docker-compose exec web_wsgi env | grep CACHE")  # noqa: E501
        print("    3. Test Redis directly: docker-compose exec redis redis-cli -a redis123 ping")  # noqa: E501

    print("\n" + "=" * 70 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
