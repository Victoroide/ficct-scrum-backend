# Testing Documentation

**Last Updated:** November 21, 2024  
**Test Framework:** pytest + Django Test Framework  
**Total Tests:** 356 tests (6 with collection errors)  
**Coverage Target:** 15% minimum (configured in pytest.ini)

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Quick Start](#quick-start)
- [Testing Infrastructure](#testing-infrastructure)
- [Test Organization](#test-organization)
- [Test Inventory by Application](#test-inventory-by-application)
- [Test Categories](#test-categories)
- [Test Data Management](#test-data-management)
- [Running Tests](#running-tests)
- [Coverage Analysis](#coverage-analysis)
- [Known Issues](#known-issues)
- [Gaps and Recommendations](#gaps-and-recommendations)
- [Best Practices](#best-practices)

---

## Executive Summary

### Key Metrics
- **Total Test Files:** 42 test files
- **Collected Tests:** 356 tests (with 6 collection errors due to missing dependencies)
- **Apps with Tests:** 10 out of 13 applications
- **Coverage Configuration:** Minimum 15% (pytest.ini line 14)
- **Test Frameworks:** pytest, pytest-django, DRF APIClient, Factory Boy
- **Test Database:** SQLite in-memory (for speed)

### Test Distribution Summary
```
✅ authentication    - 42 tests (API, models, serializers, personal resources)
✅ projects          - 83+ tests (API, models, permissions, sprints, boards, issues)
✅ organizations     - 66 tests (API, models, permissions, invitations)
✅ ml                - 76 tests (API, services, model training/loading, S3 storage)
✅ integrations      - 35 tests (GitHub OAuth, models)
✅ reporting         - 49 tests (endpoints, models, diagram service)
✅ ai_assistant      - 50 tests (API, RAG service, security, validation)
✅ notifications     - 23 tests (Slack service, notification service)
✅ workspaces        - 14 tests (permissions, serializers)
✅ admin_tools       - 13 tests (backup tasks)
❌ logging           - No tests
❌ core              - No tests
```

### Infrastructure Health
✅ pytest configuration complete (pytest.ini)  
✅ Shared fixtures defined (conftest.py)  
✅ Test settings configured (base/settings_test.py)  
✅ Factory Boy integration (9 factory files)  
⚠️ 6 tests have import errors (missing 'moto' library, incorrect import paths)  
❌ No .coverage file found (tests not run recently with coverage)  

---

## Quick Start

### Run All Tests
```bash
# Activate virtual environment first
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Run all tests with verbose output
pytest

# Run with coverage report
pytest --cov=apps --cov=base --cov-report=html

# View coverage in browser
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows
```

### Run Specific App Tests
```bash
# Test specific application
pytest apps/projects/tests/

# Test specific file
pytest apps/projects/tests/test_issue_api.py

# Test specific test
pytest apps/projects/tests/test_issue_api.py::TestIssueAPI::test_create_issue

# Run tests matching pattern
pytest -k "issue"

# Run tests with marker
pytest -m unit
```

### Common Test Commands
```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run only permission tests
pytest -m permissions

# Show test output (print statements)
pytest -s

# Stop at first failure
pytest -x

# Run last failed tests only
pytest --lf

# Dry run (collect tests without running)
pytest --collect-only
```

---

## Testing Infrastructure

### Frameworks and Tools

**Core Testing**
- `pytest==7.4.3` - Test runner and framework
- `pytest-django==4.7.0` - Django integration for pytest
- `pytest-cov==4.1.0` - Coverage reporting

**API Testing**
- `djangorestframework==3.14.0` - DRF test client
- `rest_framework.test.APIClient` - HTTP request simulation
- `rest_framework_simplejwt` - JWT token generation for auth

**Test Data Generation**
- `factory-boy==3.3.0` - Model factory pattern
- `Faker` - Realistic fake data generation
- `factory.django.DjangoModelFactory` - Django ORM integration

**Mocking** (⚠️ Missing)
- `moto` - AWS S3 mocking (REQUIRED BUT NOT INSTALLED)
- `unittest.mock` - Standard library mocking

### Configuration Files

#### pytest.ini
**Location:** `pytest.ini` (root)

```ini
[pytest]
DJANGO_SETTINGS_MODULE = base.settings_test
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --strict-markers
    --tb=short
    --cov=apps
    --cov=base
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=15
    --disable-warnings
testpaths = apps
markers =
    unit: Unit tests
    integration: Integration tests
    permissions: Permission tests
    slow: Slow running tests
```

**Key Settings:**
- Uses `base.settings_test` (removes daphne for Windows compatibility)
- Minimum coverage: 15%
- Coverage reports: terminal + HTML
- Test discovery: `apps/` directory
- Markers: unit, integration, permissions, slow

#### conftest.py
**Location:** `conftest.py` (root)

**Shared Fixtures:**
- `django_db_setup` - SQLite in-memory database
- `api_client` - Unauthenticated API client
- `authenticated_client` - JWT-authenticated client
- `admin_client` - Admin-authenticated client

#### settings_test.py
**Location:** `base/settings_test.py`

**Test-Specific Configuration:**
- Removes `daphne` from INSTALLED_APPS (avoids Windows OpenSSL issues)
- In-memory channel layer (no Redis needed)
- Local memory cache (no Redis needed)
- Celery eager mode (synchronous task execution)
- MD5 password hasher (fast hashing for tests)

---

## Test Data Management

### Factory Boy Pattern

The project uses Factory Boy for test data generation, following the factory pattern.

#### Factory Organization
- **Location:** `apps/*/tests/factories.py`
- **Total Factories:** 35+ factories across 9 apps
- **Base Class:** `factory.django.DjangoModelFactory`

#### Common Factories

**Authentication (apps/authentication/tests/factories.py):**
```python
UserFactory            # Creates User instances
AdminUserFactory       # Creates superuser instances
UserProfileFactory     # Creates UserProfile instances
```

**Projects (apps/projects/tests/factories.py):**
```python
ProjectFactory              # Creates Project
ProjectTeamMemberFactory    # Creates team memberships
WorkflowStatusFactory       # Creates workflow statuses
IssueTypeFactory            # Creates issue types
IssueFactory                # Creates issues
SprintFactory               # Creates sprints
BoardFactory                # Creates boards
BoardColumnFactory          # Creates board columns
IssueCommentFactory         # Creates comments
IssueAttachmentFactory      # Creates attachments
IssueLinkFactory            # Creates issue links
```

**Organizations (apps/organizations/tests/factories.py):**
```python
OrganizationFactory            # Creates organizations
OrganizationMembershipFactory  # Creates memberships
OrganizationInvitationFactory  # Creates invitations
OrganizationSettingsFactory    # Creates settings
```

**Workspaces (apps/workspaces/tests/factories.py):**
```python
WorkspaceFactory           # Creates workspaces
WorkspaceMemberFactory     # Creates workspace members
```

**ML (apps/ml/tests/factories.py):**
```python
MLModelFactory                # Creates ML models
PredictionHistoryFactory      # Creates predictions
AnomalyDetectionFactory       # Creates anomaly records
```

#### Factory Usage Examples

**Basic Creation:**
```python
# Create single instance
user = UserFactory()
project = ProjectFactory()

# Create with specific values
user = UserFactory(email="test@example.com", first_name="John")

# Create multiple instances
users = UserFactory.create_batch(10)
```

**Relationships:**
```python
# Automatic relationship creation
issue = IssueFactory()  # Also creates project, status, issue_type, user

# Explicit relationship
project = ProjectFactory()
issue = IssueFactory(project=project)  # Uses existing project

# Multiple issues in same project
project = ProjectFactory()
issues = IssueFactory.create_batch(5, project=project)
```

**Fixture Pattern:**
```python
@pytest.fixture
def setup_project():
    """Create complete project with team and issues."""
    user = UserFactory()
    project = ProjectFactory()
    ProjectTeamMemberFactory(project=project, user=user, role="lead")
    
    for _ in range(10):
        IssueFactory(project=project)
    
    return {"project": project, "user": user}

def test_something(setup_project):
    project = setup_project["project"]
    assert Issue.objects.filter(project=project).count() == 10
```

---

## Test Categories Detail

### Unit Tests
**Count:** ~200 tests  
**Purpose:** Test individual functions in isolation  
**Execution Time:** <1ms each  
**Database:** Not required (use mocks)

**Example:**
```python
@pytest.mark.unit
def test_issue_full_key():
    issue = IssueFactory(project__key="TEST", key="123")
    assert issue.full_key == "TEST-123"
```

### Integration Tests
**Count:** ~100 tests  
**Purpose:** Test component interactions  
**Marker:** `@pytest.mark.integration`  
**Database:** Required  

**Example:**
```python
@pytest.mark.integration
@pytest.mark.django_db
def test_create_issue_sets_initial_status():
    project = ProjectFactory()
    initial = WorkflowStatusFactory(project=project, is_initial=True)
    issue = Issue.objects.create(project=project, title="Test")
    assert issue.status == initial
```

### API Tests
**Count:** ~150 tests  
**Purpose:** Test REST endpoints  
**Tool:** DRF APIClient  

**Example:**
```python
@pytest.mark.django_db
def test_create_issue_api(api_client):
    user = UserFactory()
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/v1/projects/issues/", data)
    assert response.status_code == 201
```

---

## Running Tests

### By Application
```bash
pytest apps/projects/tests/
pytest apps/ml/tests/
pytest apps/authentication/tests/
```

### By Test File
```bash
pytest apps/projects/tests/test_issue_api.py
pytest apps/ml/tests/test_prediction_service.py
```

### By Test Class or Function
```bash
# Single class
pytest apps/projects/tests/test_issue_api.py::TestIssueAPI

# Single test
pytest apps/projects/tests/test_issue_api.py::TestIssueAPI::test_create_issue
```

### By Marker
```bash
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m permissions       # Only permission tests
pytest -m "not slow"        # Skip slow tests
```

### By Pattern
```bash
pytest -k "issue"           # All tests with "issue" in name
pytest -k "test_create"     # All create tests
pytest -k "api and not slow" # API tests, skip slow
```

### With Coverage
```bash
# All tests with coverage
pytest --cov=apps --cov=base --cov-report=html

# Specific app coverage
pytest apps/projects/tests/ --cov=apps.projects --cov-report=term

# Missing lines report
pytest --cov=apps --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=apps --cov-fail-under=80
```

### Advanced Options
```bash
# Stop on first failure
pytest -x

# Run failed tests first
pytest --failed-first

# Run only last failed
pytest --lf

# Parallel execution (requires pytest-xdist)
pytest -n 4

# Verbose output with print statements
pytest -s -v

# Generate JUnit XML (for CI)
pytest --junit-xml=test-results.xml
```

---

## Coverage Analysis

### Current Coverage Status
⚠️ **No recent coverage run found** - `.coverage` file not present

### Running Coverage
```bash
# Generate coverage report
pytest --cov=apps --cov=base --cov-report=html

# View HTML report
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html # Windows
```

### Expected Coverage Breakdown (Estimate)
Based on test inventory:

```
Application         | Tests | Estimated Coverage
--------------------|-------|-------------------
authentication      | 42    | 60-70%
projects            | 83    | 50-60%
organizations       | 66    | 55-65%
ml                  | 76    | 40-50% (some tests broken)
integrations        | 35    | 45-55% (some tests broken)
reporting           | 49    | 40-50%
ai_assistant        | 50    | 35-45% (some tests broken)
notifications       | 23    | 50-60%
workspaces          | 14    | 30-40% (limited tests)
admin_tools         | 13    | 20-30% (limited tests)
logging             | 0     | 0% (NO TESTS)
core                | 0     | 0% (NO TESTS)
--------------------|-------|-------------------
OVERALL             | 451   | 35-45% (estimated)
```

### Critical Uncovered Code (Based on Memory)
- **Celery Tasks:** Async tasks not covered (ML retraining, notifications)
- **WebSocket Consumers:** Board consumer not tested
- **Management Commands:** Most commands lack tests
- **Middleware:** Custom middleware not tested
- **Signals:** Signal handlers partially tested
- **Services:** Some business logic services not tested

---

## Known Issues

### Import Errors (6 tests failing)

**1. Missing `moto` library (2 tests)**
```
apps/ml/tests/test_model_trainer.py - ImportError: No module named 'moto'
apps/ml/tests/test_s3_storage.py - ImportError: No module named 'moto'
```

**Fix:**
```bash
pip install moto[s3]==4.2.0
```

**2. Incorrect import paths (4 tests)**
```
apps/ai_assistant/tests/test_security.py - ModuleNotFoundError: No module named 'tests'
apps/ai_assistant/tests/test_similar_issues_validation.py - ModuleNotFoundError: No module named 'apps.ai_assistant.factories'
apps/integrations/tests/test_github_oauth.py - ModuleNotFoundError: No module named 'apps.users'
apps/reporting/tests/test_report_endpoints.py - ModuleNotFoundError: No module named 'apps.users'
```

**Fixes:**
- test_security.py: Change `from tests.factories import` to `from apps.projects.tests.factories import`
- test_similar_issues_validation.py: Create missing `apps/ai_assistant/tests/factories.py` or fix import
- test_github_oauth.py: Change `from apps.users.models import User` to `from django.contrib.auth import get_user_model`
- test_report_endpoints.py: Same fix as above

### Django Shell Issues (Windows)
```
AttributeError: module 'lib' has no attribute 'SSL_MODE_ACCEPT_MOVING_WRITE_BUFFER'
```

**Cause:** Daphne/Twisted/OpenSSL compatibility issue on Windows

**Workaround:** Tests use `base.settings_test` which removes Daphne

### Slow Tests
Some integration tests may be slow (>5 seconds). Mark them:
```python
@pytest.mark.slow
def test_expensive_operation():
    # ... slow test ...
```

Then skip: `pytest -m "not slow"`

---

## Gaps and Recommendations

### Apps Without Tests (CRITICAL)

**1. apps/logging (0 tests)**
**Recommended Tests:**
- Request logging middleware
- Performance monitoring
- Error tracking and alerting
- Log rotation and cleanup

**2. apps/core (0 tests)**
**Recommended Tests:**
- Base model classes
- Custom validators
- Utility functions
- Common mixins

### Partially Tested Areas

**1. Celery Tasks**
- ML model retraining tasks (apps/ml/tasks.py)
- Notification batch sending
- Report generation tasks
- Scheduled cleanup tasks

**2. WebSocket/Channels**
- Board consumer (apps/projects/consumers/board_consumer.py)
- WebSocket authentication (JWTAuthMiddleware)
- Real-time event broadcasting

**3. Management Commands**
- Most commands lack comprehensive tests
- Only test_personal_resources.py exists

**4. Signal Handlers**
- Workflow transition creation signals
- Activity log creation signals
- Default resource creation signals

**5. External API Integration**
- GitHub API sync (partially tested)
- OpenAI API (AI assistant)
- Slack webhook delivery
- AWS S3 operations (some tests broken due to missing moto)

### Missing Test Types

**1. End-to-End Tests**
- No Selenium/Playwright tests
- No full user journey tests
- Recommendation: Add Playwright for critical flows

**2. Load/Performance Tests**
- No load testing
- No performance benchmarks
- Recommendation: Add locust or pytest-benchmark

**3. Security Tests**
- Limited penetration testing
- No automated security scans
- Recommendation: Add bandit, safety checks

**4. Database Migration Tests**
- No migration rollback tests
- No data migration tests

### Coverage Goals

**Short Term (3 months):**
- Fix all 6 import errors ✅
- Add tests for apps/logging ✅
- Add tests for apps/core ✅
- Reach 50% overall coverage

**Medium Term (6 months):**
- Add Celery task tests
- Add WebSocket consumer tests
- Add E2E tests for critical flows
- Reach 65% overall coverage

**Long Term (12 months):**
- Comprehensive test suite
- Performance benchmarks
- Security test automation
- Reach 80% overall coverage

---

## Best Practices

### 1. Test Isolation
Each test should be independent:
```python
# ✅ Good - creates own data
def test_issue_creation():
    project = ProjectFactory()
    issue = IssueFactory(project=project)
    assert issue.project == project

# ❌ Bad - depends on test order
def test_issue_list():
    issues = Issue.objects.all()
    assert issues.count() > 0  # Assumes data exists
```

### 2. Use Factories, Not Fixtures (for data)
```python
# ✅ Good - flexible, reusable
def test_something():
    user = UserFactory(is_active=True)
    project = ProjectFactory(lead=user)

# ❌ Less flexible - fixed data
@pytest.fixture
def user():
    return User.objects.create(email="test@example.com")
```

### 3. Clear Test Names
```python
# ✅ Good - descriptive
def test_workspace_member_can_access_all_workspace_projects():
    ...

# ❌ Bad - vague
def test_access():
    ...
```

### 4. Arrange-Act-Assert Pattern
```python
def test_issue_transition():
    # Arrange - set up test data
    issue = IssueFactory(status__category="to_do")
    new_status = WorkflowStatusFactory(category="in_progress")
    
    # Act - perform action
    issue.status = new_status
    issue.save()
    
    # Assert - verify result
    assert issue.status == new_status
    assert issue.status.category == "in_progress"
```

### 5. Test One Thing Per Test
```python
# ✅ Good - focused
def test_issue_creation_sets_reporter():
    user = UserFactory()
    issue = IssueFactory(reporter=user)
    assert issue.reporter == user

def test_issue_creation_sets_initial_status():
    issue = IssueFactory()
    assert issue.status.is_initial is True

# ❌ Bad - testing multiple things
def test_issue_creation():
    user = UserFactory()
    issue = IssueFactory(reporter=user)
    assert issue.reporter == user
    assert issue.status.is_initial is True
    assert issue.created_at is not None
```

### 6. Use Markers Appropriately
```python
@pytest.mark.unit  # Fast, isolated
def test_utility_function():
    ...

@pytest.mark.integration  # Multiple components
@pytest.mark.django_db
def test_api_workflow():
    ...

@pytest.mark.slow  # Long-running
@pytest.mark.django_db
def test_bulk_import():
    ...
```

### 7. Mock External Services
```python
# ✅ Good - mocked external API
@patch('apps.integrations.services.github_service.Github')
def test_github_sync(mock_github):
    mock_github.return_value.get_repo.return_value = MagicMock()
    service.sync_commits()
    mock_github.assert_called_once()

# ❌ Bad - makes real API call
def test_github_sync_real():
    service.sync_commits()  # Calls real GitHub API
```

### 8. Keep Tests Fast
- Use in-memory database (SQLite)
- Mock slow operations
- Mark slow tests with `@pytest.mark.slow`
- Run slow tests separately in CI

---

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install moto[s3]==4.2.0
      
      - name: Run tests with coverage
        run: |
          pytest --cov=apps --cov=base --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest -x --ff  # Stop on first failure, run failed first
```

---

## Maintenance

### Regular Tasks

**Daily (Developers):**
- Run tests before committing: `pytest -x --ff`
- Fix failing tests immediately
- Add tests for new features

**Weekly (Team):**
- Review test coverage report
- Fix import errors
- Add tests for uncovered critical code

**Monthly (Team Lead):**
- Review and update this documentation
- Analyze slow tests and optimize
- Review test metrics and set goals

**Quarterly (Team):**
- Refactor test suite
- Update test dependencies
- Remove obsolete tests

### Test Metrics to Track
- Total test count
- Test execution time
- Coverage percentage
- Failing test count
- Flaky test identification

---

## Conclusion

The backend test suite provides solid coverage for core functionality with 356 tests across 10 applications. Key areas requiring attention:

1. **Fix Import Errors:** Install `moto` and fix import paths (6 tests)
2. **Add Tests:** logging app, core app (0 tests currently)
3. **Increase Coverage:** From estimated 35-45% to 65%+
4. **Add E2E Tests:** Critical user flows
5. **Performance Tests:** Load testing and benchmarks

The test infrastructure is well-organized with pytest, Factory Boy, and DRF test tools. Continue building on this foundation to reach comprehensive test coverage.

---

**Document Maintained By:** Backend Team  
**Next Review:** December 21, 2024
