"""
Comprehensive tests for DiagramService.
"""

from django.utils import timezone

import pytest

from apps.projects.tests.factories import ProjectFactory
from apps.reporting.services.diagram_service import DiagramService


@pytest.mark.django_db
class TestDiagramService:
    """Test diagram service methods."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = DiagramService()
        self.project = ProjectFactory()

    def test_get_status_color(self):
        """Test status color mapping."""
        assert self.service._get_status_color("todo") == "#6c757d"
        assert self.service._get_status_color("in_progress") == "#007bff"
        assert self.service._get_status_color("done") == "#28a745"
        assert self.service._get_status_color("backlog") == "#ffc107"
        assert self.service._get_status_color("unknown") == "#6c757d"

    def test_generate_cache_key(self):
        """Test cache key generation."""
        key1 = self.service._generate_cache_key("workflow", self.project.id)
        key2 = self.service._generate_cache_key("workflow", self.project.id)

        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 32

    def test_generate_svg_from_graph(self):
        """Test SVG generation from graph data."""
        graph_data = {
            "nodes": [
                {"label": "Node 1", "color": "#007bff"},
                {"label": "Node 2", "color": "#28a745"},
            ],
            "edges": [],
        }

        svg = self.service._generate_svg_from_graph(graph_data)

        assert "<svg" in svg
        assert "</svg>" in svg
        assert "Node 1" in svg
        assert "Node 2" in svg

    def test_generate_roadmap_svg(self):
        """Test roadmap SVG generation."""
        roadmap_data = {
            "sprints": [
                {"name": "Sprint 1", "epics": []},
                {"name": "Sprint 2", "epics": []},
            ]
        }

        svg = self.service._generate_roadmap_svg(roadmap_data)

        assert "<svg" in svg
        assert "</svg>" in svg
        assert "Project roadmap" in svg

    def test_generate_uml_svg(self):
        """Test UML SVG generation."""
        uml_data = {"classes": [], "relationships": []}

        svg = self.service._generate_uml_svg(uml_data)

        assert "<svg" in svg
        assert "</svg>" in svg
        assert "UML Class Diagram" in svg

    def test_generate_architecture_svg(self):
        """Test architecture SVG generation."""
        arch_data = {"modules": []}

        svg = self.service._generate_architecture_svg(arch_data)

        assert "<svg" in svg
        assert "</svg>" in svg
        assert "Architecture Diagram" in svg
