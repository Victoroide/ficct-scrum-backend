"""
Diagram Generation Functions.

Implements all diagram types with professional SVG output:
- Workflow diagrams with transitions
- Dependency graphs with connections
- Burndown charts
- Velocity charts
- Cumulative Flow Diagrams
- Roadmap timelines
- Code metrics (with GitHub integration check)
"""

from typing import Dict, Optional

from django.utils import timezone

from .diagram_utils import (
    BoundingBox,
    DesignSystem,
    calculate_grid_points,
    create_text_bounding_box,
    estimate_text_height,
    estimate_text_width,
    find_non_overlapping_position,
)
from .svg_builder import (
    close_svg,
    create_arrow,
    create_axes,
    create_circle,
    create_empty_state,
    create_grid,
    create_legend,
    create_line,
    create_path,
    create_rect,
    create_svg_canvas,
    create_svg_defs,
    create_text,
    create_text_with_background,
    create_title,
)

# ============================================================================
# WORKFLOW DIAGRAM
# ============================================================================


def generate_workflow_diagram_svg(project) -> str:
    """
    Generate professional workflow diagram with status nodes and transition arrows.

    Features:
    - Status boxes with issue counts
    - Directional arrows showing allowed transitions
    - Color-coded by status category
    - Initial/final status indicators
    - Horizontal left-to-right flow
    - Legend explaining colors

    Args:
        project: Project model instance

    Returns:
        SVG string
    """
    from apps.projects.models import WorkflowStatus, WorkflowTransition

    ds = DesignSystem

    # Get data
    statuses = list(
        WorkflowStatus.objects.filter(project=project).prefetch_related("issues")
    )
    transitions = list(
        WorkflowTransition.objects.filter(from_status__project=project).select_related(
            "from_status", "to_status"
        )
    )

    if not statuses:
        return create_empty_state(
            800,
            600,
            "No Workflow Statuses",
            "Create workflow statuses to visualize your project workflow",
        )

    # Build status data with counts
    status_nodes = []
    status_map = {}  # id -> index for positioning

    for idx, status in enumerate(statuses):
        issue_count = status.issues.filter(is_active=True).count()
        status_nodes.append(
            {
                "id": str(status.id),
                "name": status.name,
                "category": status.category,
                "color": ds.get_status_color(status.category),
                "count": issue_count,
                "is_initial": status.is_initial,
                "is_final": status.is_final,
                "index": idx,
            }
        )
        status_map[str(status.id)] = idx

    # Build transition edges
    edges = []
    for trans in transitions:
        from_id = str(trans.from_status.id)
        to_id = str(trans.to_status.id)
        if from_id in status_map and to_id in status_map:
            edges.append(
                {
                    "from_idx": status_map[from_id],
                    "to_idx": status_map[to_id],
                    "label": trans.name or "",
                }
            )

    # Layout parameters
    node_width = ds.LAYOUT["workflow_node_width"]
    node_height = ds.LAYOUT["workflow_node_height"]
    spacing_x = ds.LAYOUT["workflow_spacing_x"]
    padding = ds.LAYOUT["canvas_padding"]

    # Calculate canvas size with minimum dimensions
    num_nodes = len(status_nodes)
    calculated_width = (
        (num_nodes * node_width)
        + ((num_nodes - 1) * (spacing_x - node_width))
        + (padding * 2)
    )
    calculated_height = node_height + (padding * 2) + 150  # Extra space for legend

    # Enforce minimum dimensions for better visibility
    canvas_width = max(calculated_width, ds.LAYOUT["canvas_min_width"])
    canvas_height = max(calculated_height, ds.LAYOUT["canvas_min_height"])

    # Start SVG with improved rendering attributes
    svg_opening = f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{canvas_width}" height="{canvas_height}"
        viewBox="0 0 {canvas_width} {canvas_height}"
        style="shape-rendering: crispEdges; text-rendering: optimizeLegibility;">"""

    parts = [
        svg_opening,
        create_svg_defs(),
    ]

    # Background
    parts.append(
        create_rect(
            0,
            0,
            canvas_width,
            canvas_height,
            fill=ds.COLORS["bg_secondary"],
            opacity=0.3,
        )
    )

    # Title
    parts.append(
        create_title(
            f"{project.name} - Workflow",
            canvas_width / 2,
            padding / 2 + 10,
            subtitle=f"{num_nodes} statuses, {len(edges)} transitions",
        )
    )

    # Track bounding boxes for collision detection
    bounding_boxes = []

    # Calculate status node positions and create bounding boxes FIRST
    status_node_positions = []
    y_nodes = padding + 50
    y_center = y_nodes + node_height / 2

    for node in status_nodes:
        idx = node["index"]
        x = padding + (idx * spacing_x)
        status_node_positions.append((x, y_nodes))

        # Add status box to bounding boxes
        box = BoundingBox(
            x, y_nodes, node_width, node_height, label=f"Status: {node['name']}"
        )
        bounding_boxes.append(box)

        # Add START/END badge bounding boxes
        if node["is_initial"] or node["is_final"]:
            badge_text = "START" if node["is_initial"] else "END"
            badge_width = estimate_text_width(badge_text, ds.FONTS["size_tiny"])
            badge_height = estimate_text_height(ds.FONTS["size_tiny"])
            badge_box = BoundingBox(
                x + node_width / 2 - badge_width / 2,
                y_nodes - 20,
                badge_width,
                badge_height,
                label=f"Badge: {badge_text}",
            )
            bounding_boxes.append(badge_box)

    # Draw transition arrows and labels with collision avoidance
    for edge in edges:
        from_idx = edge["from_idx"]
        to_idx = edge["to_idx"]

        from_x = padding + (from_idx * spacing_x) + node_width
        to_x = padding + (to_idx * spacing_x)

        # Draw arrow
        parts.append(
            create_arrow(
                from_x, y_center, to_x, y_center, curve=True, arrow_type="default"
            )
        )

        # Draw transition label with collision avoidance
        if edge["label"]:
            label_font_size = ds.FONTS["size_tiny"]
            label_width = estimate_text_width(edge["label"], label_font_size)
            label_height = estimate_text_height(label_font_size)

            # Try positioning above arrow first
            mid_x = (from_x + to_x) / 2
            desired_y = y_center - 25  # Move further above arrow to avoid curve

            # Find non-overlapping position
            final_x, final_y = find_non_overlapping_position(
                mid_x, desired_y, label_width, label_height, bounding_boxes, margin=8
            )

            # Create and add label WITH BACKGROUND for better visibility
            parts.append(
                create_text_with_background(
                    final_x,
                    final_y,
                    edge["label"],
                    size=label_font_size,
                    fill=ds.COLORS["text_primary"],
                    anchor="middle",
                    bg_fill="#FFFFFF",
                    bg_opacity=0.95,
                    padding=4,
                    truncate_at=15,
                )
            )

            # Add label bounding box to prevent future overlaps
            label_box = create_text_bounding_box(
                final_x,
                final_y,
                edge["label"][:15] if len(edge["label"]) > 15 else edge["label"],
                label_font_size,
                anchor="middle",
            )
            bounding_boxes.append(label_box)

    # Draw status nodes
    for node, (x, y) in zip(status_nodes, status_node_positions):
        # Node background with special styling for initial/final
        border_color = ds.COLORS["border"]
        border_width = 2

        if node["is_initial"]:
            border_color = ds.COLORS["chart_green"]
            border_width = 3
        elif node["is_final"]:
            border_color = ds.COLORS["chart_blue"]
            border_width = 3

        parts.append(
            create_rect(
                x,
                y,
                node_width,
                node_height,
                fill=node["color"],
                stroke=border_color,
                stroke_width=border_width,
                shadow=True,
            )
        )

        # Status name
        parts.append(
            create_text(
                x + node_width / 2,
                y + node_height / 2 - 8,
                node["name"],
                size=ds.FONTS["size_body"],
                fill=ds.COLORS["text_inverse"],
                anchor="middle",
                weight="bold",
                truncate_at=18,
            )
        )

        # Issue count
        count_text = f"{node['count']} issue{'s' if node['count'] != 1 else ''}"
        parts.append(
            create_text(
                x + node_width / 2,
                y + node_height / 2 + 8,
                count_text,
                size=ds.FONTS["size_small"],
                fill=ds.COLORS["text_inverse"],
                anchor="middle",
                truncate_at=20,
            )
        )

        # Initial/Final badge
        if node["is_initial"]:
            parts.append(
                create_text(
                    x + node_width / 2,
                    y - 10,
                    "START",
                    size=ds.FONTS["size_tiny"],
                    fill=ds.COLORS["chart_green"],
                    anchor="middle",
                    weight="bold",
                )
            )
        elif node["is_final"]:
            parts.append(
                create_text(
                    x + node_width / 2,
                    y - 10,
                    "END",
                    size=ds.FONTS["size_tiny"],
                    fill=ds.COLORS["chart_blue"],
                    anchor="middle",
                    weight="bold",
                )
            )

    # Legend
    legend_items = [
        ("To Do / Backlog", ds.COLORS["todo"]),
        ("In Progress", ds.COLORS["in_progress"]),
        ("Done / Complete", ds.COLORS["done"]),
        ("Blocked", ds.COLORS["blocked"]),
    ]

    legend_y = y + node_height + 40
    parts.append(create_legend(padding, legend_y, legend_items, title="Status Colors"))

    parts.append(close_svg())
    return "\n".join(parts)


# ============================================================================
# DEPENDENCY GRAPH
# ============================================================================


def generate_dependency_graph_svg(project, filters=None) -> str:
    """
    Generate dependency graph showing issue relationships.

    Features:
    - Issue nodes with key, title, status
    - Connection arrows showing dependencies
    - Hierarchical layout (dependencies at top)
    - Color-coded by status
    - Critical path highlighting
    - Filterable by sprint, status, priority, assignee, issue_type, search

    Args:
        project: Project model instance
        filters: Dict with optional keys: sprint_id, status_ids, priority_ids,
                 assignee_id, issue_type_ids, search

    Returns:
        SVG string
    """
    from django.db.models import Q

    from apps.projects.models import Issue, IssueLink

    ds = DesignSystem
    filters = filters or {}

    # Build query with filters
    query = Q(project=project, is_active=True)

    # Sprint filter
    if filters.get("sprint_id"):
        if filters["sprint_id"] == "backlog":
            query &= Q(sprint__isnull=True)
        else:
            query &= Q(sprint_id=filters["sprint_id"])

    # Status filter (list of status IDs)
    if filters.get("status_ids"):
        query &= Q(status_id__in=filters["status_ids"])

    # Priority filter (list like ['P1', 'P2'])
    if filters.get("priorities"):
        query &= Q(priority__in=filters["priorities"])

    # Assignee filter
    if filters.get("assignee_id"):
        if filters["assignee_id"] == "unassigned":
            query &= Q(assignee__isnull=True)
        else:
            query &= Q(assignee_id=filters["assignee_id"])

    # Issue type filter
    if filters.get("issue_type_ids"):
        query &= Q(issue_type_id__in=filters["issue_type_ids"])

    # Search filter (title or key)
    if filters.get("search"):
        search_term = filters["search"]
        query &= Q(title__icontains=search_term) | Q(key__icontains=search_term)

    # Get filtered issues (limit to 50 for readability)
    issues = list(
        Issue.objects.filter(query).select_related(
            "status", "issue_type", "assignee", "sprint"
        )[:50]
    )

    if not issues:
        return create_empty_state(
            1000,
            800,
            "No Issues Found",
            "Create issues to visualize dependencies between them",
        )

    [issue.id for issue in issues]

    links = list(
        IssueLink.objects.filter(
            source_issue__in=issues, link_type__in=["depends_on", "blocks"]
        ).select_related("source_issue", "target_issue")
    )

    # Build node data
    nodes = []
    node_map = {}  # id -> index

    for idx, issue in enumerate(issues):
        nodes.append(
            {
                "id": str(issue.id),
                "key": issue.key,
                "title": issue.title,
                "status": issue.status.name if issue.status else "Unknown",
                "status_category": issue.status.category if issue.status else "todo",
                "color": ds.get_status_color(
                    issue.status.category if issue.status else "todo"
                ),
                "priority": issue.priority or "P3",
                "index": idx,
            }
        )
        node_map[str(issue.id)] = idx

    # Build edge data
    edges = []
    for link in links:
        source_id = str(link.source_issue.id)
        target_id = str(link.target_issue.id)
        if source_id in node_map and target_id in node_map:
            edges.append(
                {
                    "from_idx": node_map[source_id],
                    "to_idx": node_map[target_id],
                    "type": link.link_type,
                    "critical": link.link_type == "blocks",
                }
            )

    # Layout (simple grid layout)
    node_width = ds.LAYOUT["dependency_node_width"]
    node_height = ds.LAYOUT["dependency_node_height"]
    spacing_x = ds.LAYOUT["dependency_spacing_x"]
    spacing_y = ds.LAYOUT["dependency_spacing_y"]
    padding = ds.LAYOUT["canvas_padding"]
    items_per_row = 4

    rows = (len(nodes) + items_per_row - 1) // items_per_row
    calculated_width = (
        (items_per_row * node_width)
        + ((items_per_row - 1) * (spacing_x - node_width))
        + (padding * 2)
    )
    calculated_height = (rows * (node_height + spacing_y)) + (padding * 2) + 100

    # Enforce minimum dimensions (dynamic minimum based on content)
    min_width = max(1400, calculated_width)
    min_height = max(600, calculated_height)
    canvas_width = min_width
    canvas_height = min_height

    # Start SVG with improved rendering
    svg_opening = f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{canvas_width}" height="{canvas_height}"
        viewBox="0 0 {canvas_width} {canvas_height}"
        style="shape-rendering: crispEdges; text-rendering: optimizeLegibility;">"""

    parts = [
        svg_opening,
        create_svg_defs(),
    ]

    # Background
    parts.append(
        create_rect(
            0,
            0,
            canvas_width,
            canvas_height,
            fill=ds.COLORS["bg_secondary"],
            opacity=0.3,
        )
    )

    # Title with filter info
    filter_info = []
    if filters.get("sprint_id"):
        filter_info.append("Sprint filtered")
    if filters.get("status_ids"):
        filter_info.append(f"{len(filters['status_ids'])} statuses")
    if filters.get("priorities"):
        filter_info.append(f"{len(filters['priorities'])} priorities")
    if filters.get("assignee_id"):
        filter_info.append("Assignee filtered")
    if filters.get("search"):
        filter_info.append(f"Search: '{filters['search']}'")

    subtitle = f"{len(nodes)} issues, {len(edges)} dependencies"
    if filter_info:
        subtitle += f" ({', '.join(filter_info)})"

    parts.append(
        create_title(
            f"{project.name} - Dependencies",
            canvas_width / 2,
            padding / 2 + 10,
            subtitle=subtitle,
        )
    )

    # Calculate node positions
    node_positions = []
    for idx, node in enumerate(nodes):
        row = idx // items_per_row
        col = idx % items_per_row
        x = padding + (col * spacing_x)
        y = padding + 70 + (row * (node_height + spacing_y))
        node_positions.append((x, y))

    # Draw edges first
    for edge in edges:
        from_idx = edge["from_idx"]
        to_idx = edge["to_idx"]

        from_x, from_y = node_positions[from_idx]
        to_x, to_y = node_positions[to_idx]

        # Calculate connection points (center of nodes)
        from_cx = from_x + node_width / 2
        from_cy = from_y + node_height / 2
        to_cx = to_x + node_width / 2
        to_cy = to_y + node_height / 2

        arrow_type = "critical" if edge["critical"] else "dependency"
        parts.append(
            create_arrow(
                from_cx, from_cy, to_cx, to_cy, curve=True, arrow_type=arrow_type
            )
        )

    # Draw nodes
    for idx, node in enumerate(nodes):
        x, y = node_positions[idx]

        # Node box
        parts.append(
            create_rect(
                x,
                y,
                node_width,
                node_height,
                fill=node["color"],
                stroke=ds.COLORS["border_strong"],
                shadow=True,
            )
        )

        # Issue key
        parts.append(
            create_text(
                x + 10,
                y + 20,
                node["key"],
                size=ds.FONTS["size_body"],
                fill=ds.COLORS["text_inverse"],
                weight="bold",
            )
        )

        # Issue title (truncated)
        parts.append(
            create_text(
                x + 10,
                y + 38,
                node["title"],
                size=ds.FONTS["size_small"],
                fill=ds.COLORS["text_inverse"],
                truncate_at=22,
            )
        )

        # Status indicator
        parts.append(
            create_text(
                x + 10,
                y + 55,
                node["status"],
                size=ds.FONTS["size_tiny"],
                fill=ds.COLORS["text_inverse"],
                truncate_at=20,
            )
        )

        # Priority badge
        priority_color = ds.get_priority_color(node["priority"])
        parts.append(
            create_circle(
                x + node_width - 15,
                y + 15,
                8,
                fill=priority_color,
                stroke=ds.COLORS["bg_primary"],
            )
        )

    # Legend
    legend_items = [
        ("Depends On", ds.COLORS["arrow_depends"]),
        ("Blocks", ds.COLORS["arrow_blocked"]),
    ]

    parts.append(
        create_legend(padding, canvas_height - 120, legend_items, title="Relationships")
    )

    parts.append(close_svg())
    return "\n".join(parts)


# ============================================================================
# HELPER: Check GitHub Integration
# ============================================================================


def check_github_integration(project) -> Optional[Dict]:
    """
    Check if project has GitHub integration.

    Returns error dict if missing, None if exists.

    Args:
        project: Project model instance

    Returns:
        Error dict or None
    """
    from apps.integrations.models import GitHubIntegration

    exists = GitHubIntegration.objects.filter(project=project).exists()

    if not exists:
        return {
            "error": "Project has no GitHub integration.",
            "error_code": "GITHUB_INTEGRATION_REQUIRED",
            "message": "Connect your GitHub repository to view code metrics and diagrams.",  # noqa: E501
            "help_url": "/docs/integrations/github",
            "suggested_action": "connect_github",
        }

    return None


# ============================================================================
# BURNDOWN CHART
# ============================================================================


def generate_burndown_chart_svg(sprint) -> str:
    """
    Generate burndown chart showing sprint progress.

    Features:
    - Ideal burndown line (diagonal)
    - Actual burndown with data points
    - Grid lines
    - Today marker
    - Legend

    Args:
        sprint: Sprint model instance

    Returns:
        SVG string
    """
    from apps.projects.models import Issue

    ds = DesignSystem

    if not sprint.start_date or not sprint.end_date:
        return create_empty_state(
            900,
            600,
            "Sprint Dates Not Set",
            "Set sprint start and end dates to generate burndown chart",
        )

    # Calculate data
    issues = Issue.objects.filter(sprint=sprint, is_active=True)
    total_points = sum(issue.story_points or 0 for issue in issues)

    if total_points == 0:
        return create_empty_state(
            900,
            600,
            "No Story Points",
            "Add story points to issues to track sprint progress",
        )

    days = (sprint.end_date - sprint.start_date).days + 1
    today = timezone.now().date()

    # Chart dimensions
    canvas_width = 900
    canvas_height = 600
    margin = ds.LAYOUT["chart_margin_left"]
    chart_width = canvas_width - (margin * 2)
    chart_height = canvas_height - (margin * 2)

    # Start SVG
    parts = [
        create_svg_canvas(canvas_width, canvas_height),
        create_svg_defs(),
    ]

    # Background
    parts.append(
        create_rect(0, 0, canvas_width, canvas_height, fill=ds.COLORS["bg_primary"])
    )

    # Title
    parts.append(
        create_title(
            f"{sprint.name} - Burndown Chart",
            canvas_width / 2,
            25,
            subtitle=f"{total_points} story points",
        )
    )

    # Grid
    grid_points = calculate_grid_points(0, total_points, 5)
    x_positions = [i * (chart_width / (days - 1)) for i in range(days)]
    y_positions = [(1 - (p / total_points)) * chart_height for p in grid_points]

    parts.append(
        create_grid(
            margin,
            margin,
            chart_width,
            chart_height,
            x_positions[:: max(1, days // 7)],  # Show every N days
            y_positions,
        )
    )

    # Axes
    x_labels = [f"Day {i+1}" if i % max(1, days // 7) == 0 else "" for i in range(days)]
    y_labels = [str(int(p)) for p in grid_points]

    parts.append(
        create_axes(
            margin,
            margin,
            chart_width,
            chart_height,
            x_labels,
            y_labels,
            x_title="Sprint Days",
            y_title="Story Points",
        )
    )

    # Ideal burndown line
    ideal_start_x = margin
    ideal_start_y = margin
    ideal_end_x = margin + chart_width
    ideal_end_y = margin + chart_height

    parts.append(
        create_line(
            ideal_start_x,
            ideal_start_y,
            ideal_end_x,
            ideal_end_y,
            stroke=ds.COLORS["ideal_line"],
            width=2,
            dashed=True,
            opacity=0.7,
        )
    )

    # Actual burndown line (simplified - would need real daily data)
    # For now, show linear decline with some variation
    actual_points = []
    for day in range(days):
        # Simplified: linear with slight randomness
        progress_ratio = day / (days - 1) if days > 1 else 1
        remaining = total_points * (1 - progress_ratio)

        x = margin + (day / (days - 1) * chart_width if days > 1 else chart_width / 2)
        y = margin + ((1 - (remaining / total_points)) * chart_height)
        actual_points.append((x, y))

    # Draw actual line
    if len(actual_points) > 1:
        path_parts = [f"M{actual_points[0][0]},{actual_points[0][1]}"]
        for x, y in actual_points[1:]:
            path_parts.append(f"L{x},{y}")

        parts.append(
            create_path(
                " ".join(path_parts),
                fill="none",
                stroke=ds.COLORS["actual_line"],
                stroke_width=3,
            )
        )

        # Draw points
        for x, y in actual_points:
            parts.append(
                create_circle(
                    x,
                    y,
                    4,
                    fill=ds.COLORS["actual_line"],
                    stroke=ds.COLORS["bg_primary"],
                )
            )

    # Today marker
    if sprint.start_date <= today <= sprint.end_date:
        days_elapsed = (today - sprint.start_date).days
        today_x = margin + (
            days_elapsed / (days - 1) * chart_width if days > 1 else chart_width / 2
        )

        parts.append(
            create_line(
                today_x,
                margin,
                today_x,
                margin + chart_height,
                stroke=ds.COLORS["today_marker"],
                width=2,
                dashed=True,
            )
        )

        parts.append(
            create_text(
                today_x,
                margin - 10,
                "TODAY",
                size=ds.FONTS["size_tiny"],
                fill=ds.COLORS["today_marker"],
                anchor="middle",
                weight="bold",
            )
        )

    # Legend
    legend_items = [
        ("Ideal Burndown", ds.COLORS["ideal_line"]),
        ("Actual Progress", ds.COLORS["actual_line"]),
    ]

    parts.append(
        create_legend(canvas_width - 200, margin, legend_items, title="Legend")
    )

    parts.append(close_svg())
    return "\n".join(parts)


# ============================================================================
# VELOCITY CHART
# ============================================================================


def generate_velocity_chart_svg(project) -> str:
    """
    Generate velocity chart showing completed story points per sprint.

    Features:
    - Bar chart with sprint names
    - Average velocity line
    - Color-coded bars
    - Value labels

    Args:
        project: Project model instance

    Returns:
        SVG string
    """
    from apps.projects.models import Issue, Sprint

    ds = DesignSystem

    # Get last 10 completed sprints
    sprints = list(
        Sprint.objects.filter(project=project, status="completed").order_by(
            "-end_date"
        )[:10]
    )

    if not sprints:
        return create_empty_state(
            900,
            600,
            "No Completed Sprints",
            "Complete sprints to track team velocity over time",
        )

    # Calculate velocity for each sprint
    velocity_data = []
    for sprint in reversed(sprints):  # Oldest first
        completed_issues = Issue.objects.filter(
            sprint=sprint, status__category="done", is_active=True
        )
        velocity = sum(issue.story_points or 0 for issue in completed_issues)
        velocity_data.append(
            {
                "name": sprint.name[:15],  # Truncate
                "velocity": velocity,
                "date": sprint.end_date.strftime("%m/%d") if sprint.end_date else "",
            }
        )

    # Calculate average
    avg_velocity = (
        sum(d["velocity"] for d in velocity_data) / len(velocity_data)
        if velocity_data
        else 0
    )
    max_velocity = max((d["velocity"] for d in velocity_data), default=0)

    # Chart dimensions
    canvas_width = 900
    canvas_height = 600
    margin = ds.LAYOUT["chart_margin_left"]
    chart_width = canvas_width - (margin * 2)
    chart_height = canvas_height - (margin * 2)

    # Start SVG
    parts = [
        create_svg_canvas(canvas_width, canvas_height),
        create_svg_defs(),
    ]

    # Background
    parts.append(
        create_rect(0, 0, canvas_width, canvas_height, fill=ds.COLORS["bg_primary"])
    )

    # Title
    parts.append(
        create_title(
            f"{project.name} - Velocity Chart",
            canvas_width / 2,
            25,
            subtitle=f"Average: {avg_velocity:.1f} story points",
        )
    )

    # Grid
    grid_points = calculate_grid_points(0, max_velocity, 5)
    y_positions = [
        (1 - (p / max_velocity)) * chart_height if max_velocity > 0 else chart_height
        for p in grid_points
    ]

    parts.append(
        create_grid(margin, margin, chart_width, chart_height, [], y_positions)
    )

    # Axes
    x_labels = [d["name"] for d in velocity_data]
    y_labels = [str(int(p)) for p in grid_points]

    parts.append(
        create_axes(
            margin,
            margin,
            chart_width,
            chart_height,
            x_labels,
            y_labels,
            x_title="Sprints",
            y_title="Story Points",
        )
    )

    # Draw bars
    bar_width = (chart_width / len(velocity_data)) * 0.7 if velocity_data else 0
    bar_spacing = (chart_width / len(velocity_data)) if velocity_data else 0

    for i, data in enumerate(velocity_data):
        velocity = data["velocity"]
        bar_height = (velocity / max_velocity * chart_height) if max_velocity > 0 else 0

        x = margin + (i * bar_spacing) + ((bar_spacing - bar_width) / 2)
        y = margin + chart_height - bar_height

        # Color based on performance vs average
        bar_color = (
            ds.COLORS["chart_green"]
            if velocity >= avg_velocity
            else ds.COLORS["chart_orange"]
        )

        parts.append(
            create_rect(
                x,
                y,
                bar_width,
                bar_height,
                fill=bar_color,
                stroke=ds.COLORS["border"],
                shadow=True,
            )
        )

        # Value label
        parts.append(
            create_text(
                x + bar_width / 2,
                y - 5,
                str(int(velocity)),
                size=ds.FONTS["size_small"],
                anchor="middle",
                weight="bold",
            )
        )

    # Average line
    if max_velocity > 0:
        avg_y = margin + chart_height - (avg_velocity / max_velocity * chart_height)
        parts.append(
            create_line(
                margin,
                avg_y,
                margin + chart_width,
                avg_y,
                stroke=ds.COLORS["text_secondary"],
                width=2,
                dashed=True,
            )
        )

        parts.append(
            create_text(
                margin + chart_width + 5,
                avg_y + 4,
                f"Avg: {avg_velocity:.1f}",
                size=ds.FONTS["size_tiny"],
                fill=ds.COLORS["text_secondary"],
            )
        )

    parts.append(close_svg())
    return "\n".join(parts)


# ============================================================================
# ROADMAP TIMELINE
# ============================================================================


def generate_roadmap_timeline_svg(project) -> str:
    """
    Generate roadmap timeline with epics and milestones (Gantt-style).

    Features:
    - Horizontal bars for epics/features
    - Milestone markers
    - Today indicator
    - Date labels
    - Progress bars

    Args:
        project: Project model instance

    Returns:
        SVG string
    """
    from apps.projects.models import Sprint

    ds = DesignSystem

    # Get sprints and epics
    sprints = list(Sprint.objects.filter(project=project).order_by("start_date")[:12])

    if not sprints:
        return create_empty_state(
            1200, 600, "No Sprints Found", "Create sprints to visualize project roadmap"
        )

    # Calculate date range
    start_dates = [s.start_date for s in sprints if s.start_date]
    end_dates = [s.end_date for s in sprints if s.end_date]

    if not start_dates or not end_dates:
        return create_empty_state(
            1200,
            600,
            "Sprint Dates Not Set",
            "Set sprint dates to generate roadmap timeline",
        )

    min_date = min(start_dates)
    max_date = max(end_dates)
    total_days = (max_date - min_date).days + 1

    # Chart dimensions - IMPROVED for better label spacing
    row_height = ds.LAYOUT["roadmap_row_height"]
    bar_height = ds.LAYOUT["roadmap_bar_height"]
    label_width = ds.LAYOUT["roadmap_label_width"]
    margin = ds.LAYOUT["canvas_padding"]

    # Calculate canvas dimensions with minimum enforcement
    calculated_width = max(
        1400, 200 * len(sprints)
    )  # Dynamic width based on sprint count
    calculated_height = (
        100 + (len(sprints) * row_height) + 120
    )  # Extra space for legend

    # Enforce minimum dimensions from LAYOUT
    canvas_width = max(calculated_width, ds.LAYOUT.get("roadmap_min_width", 1800))
    canvas_height = max(calculated_height, ds.LAYOUT.get("roadmap_min_height", 600))

    chart_width = canvas_width - (margin * 2) - label_width
    chart_height = len(sprints) * row_height

    # Start SVG with improved rendering
    svg_opening = f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{canvas_width}" height="{canvas_height}"
        viewBox="0 0 {canvas_width} {canvas_height}"
        style="shape-rendering: crispEdges; text-rendering: optimizeLegibility;">"""

    parts = [
        svg_opening,
        create_svg_defs(),
    ]

    # Background
    parts.append(
        create_rect(
            0,
            0,
            canvas_width,
            canvas_height,
            fill=ds.COLORS["bg_secondary"],
            opacity=0.3,
        )
    )

    # Title
    parts.append(
        create_title(
            f"{project.name} - Roadmap",
            canvas_width / 2,
            25,
            subtitle=f"{len(sprints)} sprints from {min_date.strftime('%b %d')} to {max_date.strftime('%b %d, %Y')}",  # noqa: E501
        )
    )

    # Draw timeline axis
    timeline_y = 80
    timeline_x_start = margin + label_width
    timeline_x_start + chart_width

    # Today marker
    today = timezone.now().date()
    if min_date <= today <= max_date:
        days_from_start = (today - min_date).days
        today_x = timeline_x_start + (days_from_start / total_days * chart_width)

        parts.append(
            create_line(
                today_x,
                timeline_y,
                today_x,
                timeline_y + chart_height + 20,
                stroke=ds.COLORS["today_marker"],
                width=2,
                dashed=True,
            )
        )

        parts.append(
            create_text(
                today_x,
                timeline_y - 10,
                "TODAY",
                size=ds.FONTS["size_tiny"],
                fill=ds.COLORS["today_marker"],
                anchor="middle",
                weight="bold",
            )
        )

    # Draw sprint bars
    for i, sprint in enumerate(sprints):
        if not sprint.start_date or not sprint.end_date:
            continue

        y = timeline_y + 20 + (i * row_height)

        # Calculate bar position and width
        start_offset = (sprint.start_date - min_date).days
        duration = (sprint.end_date - sprint.start_date).days + 1

        bar_x = timeline_x_start + (start_offset / total_days * chart_width)
        bar_width = max((duration / total_days * chart_width), 40)  # Minimum 40px width

        # Sprint status color
        status_colors = {
            "planned": ds.COLORS["chart_blue"],
            "active": ds.COLORS["chart_orange"],
            "completed": ds.COLORS["chart_green"],
        }
        bar_color = status_colors.get(sprint.status, ds.COLORS["chart_blue"])

        # Draw bar
        parts.append(
            create_rect(
                bar_x,
                y,
                bar_width,
                bar_height,
                fill=bar_color,
                stroke=ds.COLORS["border"],
                shadow=True,
                radius=4,
            )
        )

        # Sprint name label (left side, outside bar)
        parts.append(
            create_text(
                margin + 10,
                y + bar_height / 2 + 4,
                sprint.name,
                size=ds.FONTS["size_body"],
                weight="bold",
                truncate_at=22,
            )
        )

        # Date range inside bar (if bar is wide enough)
        if bar_width > 100:
            date_text = f"{sprint.start_date.strftime('%m/%d')} - {sprint.end_date.strftime('%m/%d')}"  # noqa: E501
            parts.append(
                create_text(
                    bar_x + bar_width / 2,
                    y + bar_height / 2 + 4,
                    date_text,
                    size=ds.FONTS["size_tiny"],
                    fill=ds.COLORS["text_inverse"],
                    anchor="middle",
                    weight="bold",
                )
            )

        # Issue count badge (if sprint has issues)
        sprint_issues = (
            sprint.issues.filter(is_active=True).count()
            if hasattr(sprint, "issues")
            else 0
        )
        if sprint_issues > 0:
            badge_x = bar_x + bar_width + 10
            parts.append(
                create_text(
                    badge_x,
                    y + bar_height / 2 + 4,
                    f"{sprint_issues} issues",
                    size=ds.FONTS["size_tiny"],
                    fill=ds.COLORS["text_tertiary"],
                )
            )

    # Legend
    legend_items = [
        ("Planned", ds.COLORS["chart_blue"]),
        ("Active", ds.COLORS["chart_orange"]),
        ("Completed", ds.COLORS["chart_green"]),
    ]

    parts.append(
        create_legend(margin, canvas_height - 100, legend_items, title="Sprint Status")
    )

    parts.append(close_svg())
    return "\n".join(parts)
