"""
Factory classes for ML models.
"""

import factory
from factory.django import DjangoModelFactory

from apps.ml.models import AnomalyDetection, MLModel, PredictionHistory


class MLModelFactory(DjangoModelFactory):
    """Factory for MLModel."""

    class Meta:
        model = MLModel

    name = factory.Sequence(lambda n: f"Model {n}")
    model_type = "effort_prediction"
    version = "1.0.0"
    is_active = True
    metadata = factory.Dict(
        {
            "accuracy": 0.85,
            "samples_count": 100,
            "project_id": None,
        }
    )
    hyperparameters = factory.Dict(
        {
            "n_estimators": 100,
            "max_depth": 10,
        }
    )


class PredictionHistoryFactory(DjangoModelFactory):
    """Factory for PredictionHistory."""

    class Meta:
        model = PredictionHistory

    model = factory.SubFactory(MLModelFactory)
    input_data = factory.Dict(
        {
            "title": "Test issue",
            "issue_type": "task",
        }
    )
    predicted_value = 8.0
    actual_value = None
    confidence = 0.75


class AnomalyDetectionFactory(DjangoModelFactory):
    """Factory for AnomalyDetection."""

    class Meta:
        model = AnomalyDetection

    project_id = factory.LazyFunction(lambda: None)
    anomaly_type = "velocity_drop"
    severity = "medium"
    status = "detected"
    affected_metric = "velocity"
    expected_value = 25.0
    actual_value = 15.0
    deviation_score = 2.5
    description = "Sprint velocity dropped significantly"
    possible_causes = ["Team capacity reduced", "More complex tasks"]
    mitigation_suggestions = ["Review sprint planning", "Check team availability"]
