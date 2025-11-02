#!/usr/bin/env python
"""
Redis Connection Validation Script

Tests all Redis connections used by the Django application:
- Django Cache
- Celery Broker
- Celery Result Backend
- Channel Layers

Usage:
    python scripts/validate_redis.py

Or inside Docker:
    docker-compose exec web_wsgi python scripts/validate_redis.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

import redis
from django.core.cache import cache
from django.conf import settings
from channels_redis.core import RedisChannelLayer


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_result(test_name, success, message=""):
    """Print test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"     └─ {message}")


def test_django_cache():
    """Test Django cache (CACHE_REDIS_URL)."""
    print_header("TEST 1: Django Cache (OAuth State Storage)")
    
    try:
        # Test set
        cache.set('test_key_validation', 'test_value', 60)
        
        # Test get
        value = cache.get('test_key_validation')
        
        if value == 'test_value':
            print_result("Django Cache Write/Read", True, f"URL: {getattr(settings, 'CACHE_REDIS_URL', 'Not using URL')}")
            
            # Clean up
            cache.delete('test_key_validation')
            return True
        else:
            print_result("Django Cache Write/Read", False, "Value mismatch")
            return False
            
    except Exception as e:
        print_result("Django Cache Connection", False, str(e))
        return False


def test_celery_broker():
    """Test Celery broker connection."""
    print_header("TEST 2: Celery Broker (Task Queue)")
    
    broker_url = settings.CELERY_BROKER_URL
    
    try:
        # Parse Redis URL
        r = redis.from_url(broker_url)
        
        # Test ping
        r.ping()
        
        # Test write/read
        r.set('celery_test_key', 'test_value', ex=60)
        value = r.get('celery_test_key')
        
        if value == b'test_value':
            print_result("Celery Broker Connection", True, broker_url)
            r.delete('celery_test_key')
            return True
        else:
            print_result("Celery Broker Connection", False, "Value mismatch")
            return False
            
    except Exception as e:
        print_result("Celery Broker Connection", False, str(e))
        print(f"     └─ URL: {broker_url}")
        return False


def test_celery_result_backend():
    """Test Celery result backend connection."""
    print_header("TEST 3: Celery Result Backend (Task Results)")
    
    result_url = settings.CELERY_RESULT_BACKEND
    
    try:
        # Parse Redis URL
        r = redis.from_url(result_url)
        
        # Test ping
        r.ping()
        
        # Test write/read
        r.set('celery_result_test_key', 'test_value', ex=60)
        value = r.get('celery_result_test_key')
        
        if value == b'test_value':
            print_result("Celery Result Backend", True, result_url)
            r.delete('celery_result_test_key')
            return True
        else:
            print_result("Celery Result Backend", False, "Value mismatch")
            return False
            
    except Exception as e:
        print_result("Celery Result Backend", False, str(e))
        print(f"     └─ URL: {result_url}")
        return False


def test_channel_layers():
    """Test Django Channels Redis layer."""
    print_header("TEST 4: Channel Layers (WebSockets)")
    
    try:
        # Get channel layer config
        channel_config = settings.CHANNEL_LAYERS.get('default', {})
        hosts = channel_config.get('CONFIG', {}).get('hosts', [])
        
        if not hosts:
            print_result("Channel Layers Config", False, "No hosts configured")
            return False
        
        # Test connection to first host
        if isinstance(hosts[0], str):
            # URL format
            redis_url = hosts[0]
            r = redis.from_url(redis_url)
        else:
            # (host, port) tuple format
            host, port = hosts[0]
            r = redis.Redis(host=host, port=port)
        
        # Test ping
        r.ping()
        
        print_result("Channel Layers Connection", True, str(hosts[0]))
        return True
        
    except Exception as e:
        print_result("Channel Layers Connection", False, str(e))
        return False


def print_environment_info():
    """Print Redis environment variables."""
    print_header("ENVIRONMENT CONFIGURATION")
    
    env_vars = [
        'CACHE_REDIS_URL',
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND',
        'CHANNEL_LAYERS_REDIS_URL',
        'REDIS_HOST',
        'REDIS_PORT',
        'REDIS_PASSWORD',
    ]
    
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        
        # Mask password
        if 'PASSWORD' in var and value != 'NOT SET':
            value = '***MASKED***'
        elif 'redis://' in value and '@' in value:
            # Mask password in URL
            parts = value.split('@')
            if ':' in parts[0]:
                protocol, auth = parts[0].rsplit(':', 1)
                value = f"{protocol}:***@{parts[1]}"
        
        print(f"  {var}: {value}")


def print_summary(results):
    """Print test summary."""
    print_header("SUMMARY")
    
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    
    print(f"\n  Total Tests: {total}")
    print(f"  Passed:      {passed} ✅")
    print(f"  Failed:      {failed} {'❌' if failed > 0 else ''}")
    
    if failed == 0:
        print("\n  🎉 ALL TESTS PASSED - Redis is configured correctly!")
        print("  GitHub OAuth, Celery tasks, and WebSockets should work.")
    else:
        print("\n  ⚠️  SOME TESTS FAILED - Redis configuration needs attention")
        print("  Review the failed tests above and check:")
        print("    - Environment variables are set correctly")
        print("    - Redis service is running")
        print("    - Network connectivity to Redis")
        print("    - Redis password is correct")
    
    print("\n" + "=" * 70 + "\n")
    
    return failed == 0


def main():
    """Run all Redis connection tests."""
    print("\n" + "=" * 70)
    print("  REDIS CONNECTION VALIDATION")
    print("  Django Scrum Backend - ficct-scrum-backend")
    print("=" * 70)
    
    # Print environment
    print_environment_info()
    
    # Run tests
    results = {
        'Django Cache': test_django_cache(),
        'Celery Broker': test_celery_broker(),
        'Celery Result Backend': test_celery_result_backend(),
        'Channel Layers': test_channel_layers(),
    }
    
    # Print summary
    success = print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
