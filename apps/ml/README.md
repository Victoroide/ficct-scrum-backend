# ML Application - Machine Learning Subsystem

## Overview

The ML application provides intelligent predictions and recommendations for project management using machine learning models. All models are trained using scikit-learn, stored in AWS S3 for scalability, and served with in-memory caching for performance.

### Key Features

- **Effort Prediction**: Predict hours required for issues using trained ML models
- **Sprint Duration Estimation**: Estimate sprint completion time based on velocity
- **Story Points Recommendation**: Suggest story points based on similar issues
- **Task Assignment**: Recommend optimal team member assignments
- **Anomaly Detection**: Identify unusual patterns and project risks
- **S3 Integration**: All models stored in S3 with versioning
- **Model Caching**: In-memory caching for fast predictions
- **Automatic Retraining**: Periodic model updates based on new data

---

## Architecture

### Service Layer Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (ViewSets)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Prediction   │  │Recommendation│  │   Anomaly    │     │
│  │   Service    │  │   Service    │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                                      │             │
│         ├──────────────────────────────────────┘             │
│         │                                                    │
│  ┌──────▼─────────┐                                         │
│  │  ModelLoader   │◄───────┐                                │
│  │  (with cache)  │        │                                │
│  └──────┬─────────┘        │                                │
│         │                  │                                │
│  ┌──────▼──────────────────┴────┐                           │
│  │   S3ModelStorageService      │                           │
│  └──────────────────────────────┘                           │
│                   │                                          │
├───────────────────┼──────────────────────────────────────────┤
│                   │                                          │
│  ┌────────────────▼──────────────┐                          │
│  │         AWS S3 Storage         │                          │
│  │  ml_models/                    │                          │
│  │  ml_datasets/                  │                          │
│  └────────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Training**: `ModelTrainer` → `S3ModelStorageService` → S3
2. **Inference**: API → `PredictionService` → `ModelLoader` (cache/S3) → Response
3. **Monitoring**: `AnomalyDetectionService` → Database → Notifications

---

## Models Implemented

### 1. Effort Prediction Model

**Purpose**: Predict hours required to complete an issue

**Algorithm**: Gradient Boosting Regressor

**Input Features**:
- Title length (words)
- Description length (words)
- Issue type (bug/story/task)
- Priority score
- Story points (if available)

**Output**: Predicted hours, confidence score, prediction range

**Training Data**: Completed issues with actual hours recorded

**Performance Metrics**:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- R² Score

**Example Usage**:
```python
from apps.ml.services import PredictionService

service = PredictionService()
result = service.predict_issue_effort(
    title="Fix authentication bug",
    description="Users cannot login",
    issue_type="bug",
    project_id="uuid-here"
)
# Returns: {
#   "predicted_hours": 8.5,
#   "confidence": 0.75,
#   "prediction_range": {"min": 6.0, "max": 11.0},
#   "method": "ml_model",
#   "model_version": "20240101_120000"
# }
```

### 2. Story Points Model

**Purpose**: Recommend story points for issues

**Algorithm**: Similarity-based recommendation with historical data

**Input**: Issue title, description, type

**Output**: Recommended points, confidence, probability distribution

**Training Data**: Completed issues with story points

### 3. Anomaly Detection

**Purpose**: Detect unusual patterns in projects and sprints

**Detections**:
- Velocity drops (statistical analysis)
- Excessive unassigned issues
- Sprint risks (burndown velocity)
- Stale issues (no updates >30 days)
- Status bottlenecks

**Algorithm**: Statistical analysis with Z-scores and thresholds

---

## S3 Configuration

### Bucket Structure

```
s3://your-bucket-name/
├── ml_models/
│   ├── effort_prediction/
│   │   ├── 1.0.0/
│   │   │   └── 20240101_120000/
│   │   │       └── model.joblib
│   │   └── 2.0.0/
│   │       └── 20240115_140000/
│   │           └── model.joblib
│   ├── story_points/
│   └── sprint_duration/
├── ml_datasets/
│   ├── project-uuid-1/
│   │   └── training_set_20240101.pkl
│   └── project-uuid-2/
│       └── training_set_20240102.pkl
```

### Required AWS Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

### Environment Variables

```bash
# Django settings.py or .env
AWS_STORAGE_BUCKET_NAME=your-ml-models-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Optional: Use IAM role instead of credentials
# (recommended for EC2/ECS deployments)
```

### S3 Configuration in Code

```python
# base/settings.py
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default=None)
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default=None)
```

---

## API Endpoints

### Base URL: `/api/v1/ml/`

### 1. Predict Effort

**Endpoint**: `POST /api/v1/ml/predict-effort/`

**Request**:
```json
{
  "title": "Fix authentication bug",
  "description": "Users cannot login",
  "issue_type": "bug",
  "project_id": "uuid-here"
}
```

**Response**:
```json
{
  "predicted_hours": 8.5,
  "confidence": 0.75,
  "prediction_range": {
    "min": 6.0,
    "max": 11.0
  },
  "method": "ml_model",
  "model_version": "1.0.0",
  "reasoning": "Prediction from trained ML model (v1.0.0)",
  "similar_issues": []
}
```

### 2. Estimate Sprint Duration

**Endpoint**: `POST /api/v1/ml/estimate-sprint-duration/`

**Request**:
```json
{
  "sprint_id": "uuid-here",
  "planned_issues": ["issue-uuid-1", "issue-uuid-2"],
  "team_capacity_hours": 160
}
```

**Response**:
```json
{
  "estimated_days": 14,
  "planned_days": 14,
  "confidence": 0.7,
  "average_velocity": 15.5,
  "total_story_points": 25,
  "risk_factors": [],
  "method": "velocity_based"
}
```

### 3. Recommend Story Points

**Endpoint**: `POST /api/v1/ml/recommend-story-points/`

**Request**:
```json
{
  "title": "Implement user profile",
  "description": "Add user profile page",
  "issue_type": "story",
  "project_id": "uuid-here"
}
```

**Response**:
```json
{
  "recommended_points": 5,
  "confidence": 0.85,
  "probability_distribution": {
    "3": 0.2,
    "5": 0.5,
    "8": 0.3
  },
  "reasoning": "Based on 10 similar issues",
  "method": "similarity"
}
```

### 4. Suggest Task Assignment

**Endpoint**: `POST /api/v1/ml/suggest-assignment/`

**Request**:
```json
{
  "issue_id": "uuid-here",
  "project_id": "uuid-here",
  "top_n": 3
}
```

**Response**:
```json
{
  "suggestions": [
    {
      "user_id": "uuid",
      "user_name": "John Doe",
      "user_email": "john@example.com",
      "total_score": 0.85,
      "skill_score": 0.9,
      "workload_score": 0.8,
      "performance_score": 0.9,
      "availability_score": 0.8,
      "reasoning": [
        "Strong experience with bug issues",
        "Currently has capacity"
      ]
    }
  ]
}
```

### 5. Detect Sprint Risks

**Endpoint**: `GET /api/v1/ml/{sprint_id}/sprint-risk/`

**Response**:
```json
{
  "risks": [
    {
      "risk_type": "burndown_velocity",
      "severity": "high",
      "description": "Sprint is 25% behind expected progress",
      "expected_completion": 50.0,
      "actual_completion": 25.0,
      "mitigation_suggestions": [
        "Consider reducing sprint scope",
        "Identify and remove blockers"
      ]
    }
  ]
}
```

### 6. Project Summary (AI-powered)

**Endpoint**: `POST /api/v1/ml/{project_id}/project-summary/`

**Response**:
```json
{
  "completion": 37.5,
  "velocity": 15.3,
  "risk_score": 23.5,
  "project_id": "uuid",
  "generated_at": "2024-01-01T00:00:00Z",
  "metrics_breakdown": {
    "total_issues": 40,
    "completed_issues": 15,
    "sprints_analyzed": 3,
    "unassigned_issues": 5,
    "overdue_issues": 3
  }
}
```

---

## Training Pipeline

### Manual Training

```python
from apps.ml.services import ModelTrainer

trainer = ModelTrainer()

# Train global model
model = trainer.train_effort_prediction_model(
    project_id=None,
    user=request.user
)

# Train project-specific model
model = trainer.train_effort_prediction_model(
    project_id="project-uuid",
    user=request.user
)
```

### Automatic Retraining

Models are automatically retrained via Celery tasks:

**Schedule**: Weekly (Monday 2 AM)

**Trigger Conditions**:
- Model age > 30 days
- 20% more training data available
- Accuracy degradation detected

**Configuration**:
```python
# base/celery.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'retrain-ml-models': {
        'task': 'apps.ml.tasks.retrain_ml_models',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),
    },
}
```

### Training Process

1. **Data Collection**: Fetch completed issues with actual hours
2. **Feature Extraction**: Extract numerical features from text and metadata
3. **Data Split**: 80% training, 20% testing
4. **Model Training**: Train Gradient Boosting Regressor
5. **Evaluation**: Calculate MAE, RMSE, R² metrics
6. **Serialization**: Serialize model with joblib
7. **S3 Upload**: Upload to S3 with versioning
8. **Database Record**: Create MLModel database entry
9. **Activation**: Mark new model as active if better than current

### Minimum Training Data

- **Effort Prediction**: 50 completed issues with actual hours
- **Story Points**: 50 completed issues with story points

---

## Inference Pipeline

### Model Loading Strategy

1. **Cache Check**: Check in-memory cache first (TTL: 1 hour)
2. **Database Query**: Find active model for type/project
3. **S3 Download**: Download model bytes from S3
4. **Deserialization**: Load model with joblib
5. **Cache Storage**: Store in memory cache for future requests

### Prediction Flow

```
Request → PredictionService
           ↓
    Try ML Model → ModelLoader → S3
           ↓ (if available)
    ML Prediction → Store History
           ↓
    Return Result

    ↓ (if unavailable)
    
    Try Similarity → Find Similar Issues
           ↓ (if found)
    Similarity Prediction
           ↓
    Return Result

    ↓ (if not found)
    
    Heuristic Fallback → Type Average
           ↓
    Return Result
```

### Prediction Methods (in order)

1. **ML Model**: Trained scikit-learn model (highest confidence)
2. **Similarity**: Jaccard similarity on completed issues
3. **Heuristic**: Average by issue type (lowest confidence)

### Caching Strategy

- **Cache Key Format**: `{model_type}_{project_id|global}`
- **TTL**: 3600 seconds (1 hour)
- **Thread-safe**: Uses threading.Lock
- **Auto-expiration**: Entries expire and are removed automatically

---

## Recommendation Engine

### Task Assignment Algorithm

**Scoring Components** (weighted):

1. **Skill Match (40%)**: Experience with issue type
2. **Workload (30%)**: Current active issues (inverse)
3. **Performance (20%)**: Completion rate
4. **Availability (10%)**: Recent activity

**Formula**:
```python
total_score = (
    skill_score * 0.4 +
    workload_score * 0.3 +
    performance_score * 0.2 +
    availability_score * 0.1
)
```

**Skill Score Calculation**:
```python
skill_score = min(
    (same_type_completed / total_completed) * 2,
    1.0
)
```

**Workload Score** (inverse):
- 0 issues: 1.0
- 1-3 issues: 0.8
- 4-6 issues: 0.5
- 7-10 issues: 0.3
- >10 issues: 0.1

---

## Development Setup

### Prerequisites

- Python 3.10+
- Django 5.0+
- AWS Account with S3 access
- PostgreSQL database

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# Key ML dependencies:
# - scikit-learn>=1.4.0
# - numpy>=1.24.0
# - pandas>=2.0.0
# - joblib>=1.3.0
# - boto3==1.34.51
# - moto[s3]==4.2.0 (for testing)

# 2. Configure environment
cp .env.example .env

# Edit .env with your AWS credentials:
AWS_STORAGE_BUCKET_NAME=your-ml-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# 3. Run migrations
python manage.py migrate ml

# 4. Create S3 bucket (if not exists)
aws s3 mb s3://your-ml-bucket --region us-east-1
```

### Local Development with S3

**Option 1: Use Real S3**
- Create development bucket
- Use separate bucket from production
- Set environment variables

**Option 2: Use LocalStack (S3 emulator)**
```bash
# Install LocalStack
pip install localstack

# Start LocalStack
localstack start

# Configure endpoint
AWS_S3_ENDPOINT_URL=http://localhost:4566
```

---

## Testing

### Running Tests

```bash
# Activate virtual environment
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run all ML tests
pytest apps/ml/tests/ -v

# Run specific test file
pytest apps/ml/tests/test_s3_storage.py -v

# Run with coverage
pytest apps/ml/tests/ --cov=apps.ml --cov-report=html

# View coverage report
# Open htmlcov/index.html in browser
```

### Test Organization

```
apps/ml/tests/
├── __init__.py
├── factories.py                      # Test data factories
├── test_api.py                       # API endpoint tests
├── test_s3_storage.py                # S3 storage tests (mocked)
├── test_model_trainer.py             # Model training tests
├── test_model_loader.py              # Model loading tests
├── test_prediction_service.py        # Original prediction tests
└── test_prediction_service_enhanced.py  # Enhanced ML prediction tests
```

### Mocking S3 in Tests

All S3 operations are mocked using `moto`:

```python
from moto import mock_s3
import boto3
import pytest

@pytest.fixture
def s3_mock():
    with mock_s3():
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-ml-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        yield bucket_name

@pytest.mark.django_db
def test_upload_model(s3_mock):
    # Test uses mocked S3, no real AWS calls
    service = S3ModelStorageService()
    # ... test code
```

### Coverage Requirements

- **Target**: 100% coverage for ML app
- **Critical Paths**: All training, inference, S3 operations
- **Edge Cases**: Error handling, fallbacks, empty data

### Test Data

Use factories for consistent test data:

```python
from apps.ml.tests.factories import MLModelFactory

# Create test model
model = MLModelFactory(
    model_type='effort_prediction',
    version='1.0.0',
    is_active=True
)
```

---

## Deployment

### Production Checklist

- [ ] S3 bucket created with proper permissions
- [ ] IAM role configured (recommended over access keys)
- [ ] Environment variables set
- [ ] Database migrations applied
- [ ] Initial models trained
- [ ] Celery workers running for background tasks
- [ ] Monitoring configured (CloudWatch, Sentry)
- [ ] Cache warmed up (preload models)

### IAM Role Configuration (Recommended)

For EC2/ECS deployments, use IAM roles instead of access keys:

```python
# No credentials needed in code
# boto3 automatically uses instance IAM role

s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)
```

### Celery Configuration

```bash
# Start Celery worker
celery -A base worker -l INFO

# Start Celery beat (scheduler)
celery -A base beat -l INFO

# Combined (development only)
celery -A base worker -B -l INFO
```

### Monitoring

**Metrics to Track**:
- Model prediction latency
- S3 upload/download times
- Cache hit rate
- Prediction accuracy (MAE/RMSE)
- Model retraining frequency
- Failed predictions

**Logging**:
```python
# All services use Python logging
import logging
logger = logging.getLogger(__name__)

logger.info("Model loaded successfully")
logger.warning("Using fallback prediction method")
logger.error("Failed to download model from S3")
```

### Performance Optimization

1. **Preload Models on Startup**:
```python
from apps.ml.services import ModelLoader

loader = ModelLoader()
loader.preload_models(['effort_prediction', 'story_points'])
```

2. **Increase Cache TTL** (if stable models):
```python
# apps/ml/services/model_loader.py
CACHE_TTL = 7200  # 2 hours instead of 1
```

3. **Use S3 Transfer Acceleration** (optional):
```python
# boto3 config
config = Config(
    s3={'use_accelerate_endpoint': True}
)
```

---

## Troubleshooting

### Issue: Models not loading

**Symptoms**: Predictions always use fallback methods

**Diagnosis**:
```python
from apps.ml.models import MLModel

# Check if active models exist
active_models = MLModel.objects.filter(is_active=True, status='active')
print(f"Active models: {active_models.count()}")

# Check S3 connectivity
from apps.ml.services import S3ModelStorageService
storage = S3ModelStorageService()
models = storage.list_models()
print(f"Models in S3: {len(models)}")
```

**Solutions**:
- Verify S3 credentials
- Check model `is_active=True` and `status='active'`
- Ensure S3 bucket exists and is accessible
- Check model has `s3_key` populated

### Issue: S3 Upload Failures

**Symptoms**: `RuntimeError: S3 upload failed`

**Diagnosis**:
```bash
# Test AWS credentials
aws s3 ls s3://your-bucket-name/

# Check IAM permissions
aws iam get-user
```

**Solutions**:
- Verify AWS credentials in environment
- Check IAM policy allows `s3:PutObject`
- Ensure bucket name is correct
- Check region matches bucket region

### Issue: Low Prediction Accuracy

**Symptoms**: High MAE/RMSE, low R² score

**Diagnosis**:
```python
from apps.ml.models import MLModel

model = MLModel.objects.filter(
    model_type='effort_prediction',
    is_active=True
).first()

print(f"MAE: {model.mae}")
print(f"RMSE: {model.rmse}")
print(f"R²: {model.r2_score}")
print(f"Training samples: {model.training_samples}")
```

**Solutions**:
- Increase training data (aim for 200+ samples)
- Clean training data (remove outliers)
- Retrain with recent data
- Use project-specific models instead of global
- Check feature engineering quality

### Issue: Slow Predictions

**Symptoms**: High latency on prediction endpoints

**Diagnosis**:
```python
from apps.ml.services import ModelLoader

loader = ModelLoader()
stats = loader.get_cache_stats()
print(f"Cached models: {stats['total_cached']}")
```

**Solutions**:
- Preload models on startup
- Increase cache TTL
- Check S3 download performance
- Use S3 transfer acceleration
- Profile with Django Debug Toolbar

### Issue: Cache Not Working

**Symptoms**: S3 downloads on every request

**Diagnosis**:
```python
from apps.ml.services import ModelLoader

loader = ModelLoader()
loader.clear_cache()

# Load model twice
model1 = loader.load_active_model('effort_prediction')
model2 = loader.load_active_model('effort_prediction')

stats = loader.get_cache_stats()
print(stats)  # Should show 1 cached item
```

**Solutions**:
- Check cache TTL not too short
- Verify thread safety (using locks)
- Check memory constraints
- Review cache key generation

### Issue: Tests Failing

**Symptoms**: S3 tests fail with connection errors

**Diagnosis**:
```bash
# Check moto installation
pip show moto

# Run single test with verbose output
pytest apps/ml/tests/test_s3_storage.py::TestS3ModelStorageService::test_upload_model -v -s
```

**Solutions**:
- Ensure `moto[s3]` installed
- Use `@mock_s3` decorator
- Check fixture setup
- Verify no real AWS credentials in test environment

---

## API Authentication

All ML endpoints require authentication:

```python
# JWT Token
headers = {
    'Authorization': 'Bearer <your-jwt-token>'
}

# Make request
response = requests.post(
    'http://localhost:8000/api/v1/ml/predict-effort/',
    headers=headers,
    json={...}
)
```

---

## Contributing

When adding new ML features:

1. **Create Service Class**: Add to `apps/ml/services/`
2. **Add Tests**: Comprehensive unit tests with S3 mocking
3. **Update Serializers**: Add response serializers
4. **Document API**: Add to this README
5. **Add Migrations**: If model changes needed
6. **Update Factories**: For test data generation

---

## License

Internal use only. Proprietary software for FICCT Scrum Backend.

---

## Support

For issues or questions:
- Check this README first
- Review test files for usage examples
- Check Django logs for detailed errors
- Contact backend team for assistance

---

**Last Updated**: 2024-01-19
**Version**: 2.0.0
**Maintainer**: Backend Team
