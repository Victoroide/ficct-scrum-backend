"""
SVG Element Builder Utilities.

Provides reusable functions for building SVG elements with consistent styling,
following the design system defined in diagram_utils.py.
"""

from typing import List, Optional, Tuple

from .diagram_utils import DesignSystem, escape_svg_text, truncate_text, wrap_text

# ============================================================================
# CORE SVG STRUCTURE
# ============================================================================


def create_svg_canvas(width: int, height: int, view_box: Optional[str] = None) -> str:
    """
    Create SVG opening tag with proper namespace and viewBox.

    Args:
        width: Canvas width in pixels
        height: Canvas height in pixels
        view_box: Optional custom viewBox (default: "0 0 width height")

    Returns:
        SVG opening tag string
    """
    vb = view_box or f"0 0 {width} {height}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="{vb}">'
    )


def close_svg() -> str:
    """Return SVG closing tag."""
    return "</svg>"


def create_svg_defs() -> str:
    """
    Create SVG defs section with reusable elements (arrow markers, filters).

    Returns:
        SVG defs section with arrow markers and shadow filter
    """
    ds = DesignSystem
    return f"""
<defs>
    <!-- Arrow Markers -->
    <marker id="arrowhead" markerWidth="10" markerHeight="10" 
            refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="{ds.COLORS['arrow_default']}"/>
    </marker>
    <marker id="arrowhead-critical" markerWidth="10" markerHeight="10" 
            refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="{ds.COLORS['arrow_blocked']}"/>
    </marker>
    <marker id="arrowhead-dependency" markerWidth="10" markerHeight="10" 
            refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="{ds.COLORS['arrow_depends']}"/>
    </marker>
    
    <!-- Filters -->
    <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="{ds.SHAPES['shadow_offset_x']}" 
                      dy="{ds.SHAPES['shadow_offset_y']}" 
                      stdDeviation="{ds.SHAPES['shadow_blur']}" 
                      flood-opacity="{ds.SHAPES['shadow_opacity']}"/>
    </filter>
    
    <!-- Gradients -->
    <linearGradient id="grad-blue" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" style="stop-color:{ds.COLORS['chart_blue']};stop-opacity:0.8" />
        <stop offset="100%" style="stop-color:{ds.COLORS['chart_blue']};stop-opacity:0.4" />
    </linearGradient>
</defs>"""


# ============================================================================
# SHAPE ELEMENTS
# ============================================================================


def create_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    stroke: Optional[str] = None,
    stroke_width: int = 2,
    radius: int = 6,
    opacity: float = 1.0,
    shadow: bool = False,
    css_class: str = "",
) -> str:
    """
    Create a rectangle with consistent styling.

    Args:
        x, y: Top-left position
        width, height: Dimensions
        fill: Fill color
        stroke: Border color (optional)
        stroke_width: Border width
        radius: Corner radius
        opacity: Opacity (0-1)
        shadow: Add drop shadow
        css_class: Optional CSS class

    Returns:
        SVG rect element
    """
    stroke_attr = f'stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    filter_attr = 'filter="url(#shadow)"' if shadow else ""
    class_attr = f'class="{css_class}"' if css_class else ""

    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'fill="{fill}" {stroke_attr} rx="{radius}" '
        f'opacity="{opacity}" {filter_attr} {class_attr}/>'
    )


def create_circle(
    cx: float,
    cy: float,
    r: float,
    fill: str,
    stroke: Optional[str] = None,
    stroke_width: int = 2,
) -> str:
    """
    Create a circle.

    Args:
        cx, cy: Center position
        r: Radius
        fill: Fill color
        stroke: Border color (optional)
        stroke_width: Border width

    Returns:
        SVG circle element
    """
    stroke_attr = f'stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" {stroke_attr}/>'


def create_ellipse(
    cx: float, cy: float, rx: float, ry: float, fill: str, stroke: Optional[str] = None
) -> str:
    """Create an ellipse."""
    stroke_attr = f'stroke="{stroke}" stroke-width="2"' if stroke else ""
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" {stroke_attr}/>'


# ============================================================================
# TEXT ELEMENTS
# ============================================================================


def create_text(
    x: float,
    y: float,
    text: str,
    size: int = 12,
    fill: Optional[str] = None,
    anchor: str = "start",
    weight: str = "normal",
    truncate_at: Optional[int] = None,
    css_class: str = "",
) -> str:
    """
    Create text element with proper escaping and truncation.

    Args:
        x, y: Position
        text: Text content
        size: Font size
        fill: Text color (defaults to text_primary)
        anchor: Text anchor (start, middle, end)
        weight: Font weight (normal, bold, 500)
        truncate_at: Truncate text at character count
        css_class: Optional CSS class

    Returns:
        SVG text element
    """
    ds = DesignSystem
    fill = fill or ds.COLORS["text_primary"]

    if truncate_at:
        text = truncate_text(text, truncate_at)

    text = escape_svg_text(text)
    class_attr = f'class="{css_class}"' if css_class else ""

    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}" '
        f'font-family="{ds.FONTS["family"]}" {class_attr}>{text}</text>'
    )


def create_text_with_background(
    x: float,
    y: float,
    text: str,
    size: int = 12,
    fill: Optional[str] = None,
    anchor: str = "middle",
    weight: str = "normal",
    bg_fill: str = "#FFFFFF",
    bg_opacity: float = 0.9,
    padding: int = 4,
    truncate_at: Optional[int] = None,
) -> str:
    """
    Create text with background rectangle for better visibility on complex backgrounds.

    Args:
        x, y: Position
        text: Text content
        size: Font size
        fill: Text color
        anchor: Text anchor (start, middle, end)
        weight: Font weight
        bg_fill: Background color
        bg_opacity: Background opacity (0-1)
        padding: Padding around text
        truncate_at: Truncate text at character count

    Returns:
        SVG group with rect and text
    """
    from .diagram_utils import escape_svg_text, estimate_text_width, truncate_text

    ds = DesignSystem
    fill = fill or ds.COLORS["text_primary"]

    if truncate_at:
        text = truncate_text(text, truncate_at)

    # Estimate text dimensions
    text_width = estimate_text_width(text, size)
    text_height = size

    # Calculate background rectangle dimensions and position
    bg_width = text_width + (padding * 2)
    bg_height = text_height + (padding * 2)

    if anchor == "middle":
        bg_x = x - bg_width / 2
    elif anchor == "end":
        bg_x = x - bg_width
    else:  # start
        bg_x = x

    bg_y = y - text_height + (padding / 2)

    escaped_text = escape_svg_text(text)

    return f"""<g>
    <rect x="{bg_x}" y="{bg_y}" width="{bg_width}" height="{bg_height}" 
          fill="{bg_fill}" opacity="{bg_opacity}" rx="3"/>
    <text x="{x}" y="{y}" font-size="{size}" fill="{fill}" 
          text-anchor="{anchor}" font-weight="{weight}" 
          font-family="{ds.FONTS["family"]}">{escaped_text}</text>
</g>"""


def create_multiline_text(
    x: float,
    y: float,
    lines: List[str],
    size: int = 12,
    fill: Optional[str] = None,
    line_height: float = 1.4,
    anchor: str = "start",
) -> str:
    """
    Create multiline text using tspan elements.

    Args:
        x, y: Starting position
        lines: List of text lines
        size: Font size
        fill: Text color
        line_height: Line height multiplier
        anchor: Text anchor

    Returns:
        SVG text element with tspan children
    """
    ds = DesignSystem
    fill = fill or ds.COLORS["text_primary"]

    parts = [
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}" font-family="{ds.FONTS["family"]}">'
    ]

    for i, line in enumerate(lines):
        dy = 0 if i == 0 else size * line_height
        escaped_line = escape_svg_text(line)
        parts.append(f'  <tspan x="{x}" dy="{dy}">{escaped_line}</tspan>')

    parts.append("</text>")
    return "\n".join(parts)


# ============================================================================
# LINE AND PATH ELEMENTS
# ============================================================================


def create_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: Optional[str] = None,
    width: int = 2,
    dashed: bool = False,
    marker_end: Optional[str] = None,
    opacity: float = 1.0,
) -> str:
    """
    Create a line with optional arrow marker.

    Args:
        x1, y1: Start position
        x2, y2: End position
        stroke: Line color (defaults to border)
        width: Line width
        dashed: Use dashed line
        marker_end: Arrow marker ID (e.g., 'arrowhead')
        opacity: Line opacity

    Returns:
        SVG line element
    """
    ds = DesignSystem
    stroke = stroke or ds.COLORS["border"]
    dash_attr = f'stroke-dasharray="{ds.CHART["grid_line_dash"]}"' if dashed else ""
    marker_attr = f'marker-end="url(#{marker_end})"' if marker_end else ""

    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{width}" '
        f'opacity="{opacity}" {dash_attr} {marker_attr}/>'
    )


def create_arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    curve: bool = True,
    arrow_type: str = "default",
    stroke: Optional[str] = None,
    width: int = 2,
) -> str:
    """
    Create an arrow (line/path with marker).

    Args:
        x1, y1: Start position
        x2, y2: End position
        curve: Use curved path (bezier)
        arrow_type: 'default', 'critical', 'dependency'
        stroke: Custom stroke color
        width: Line width

    Returns:
        SVG line or path element with arrow marker
    """
    ds = DesignSystem

    # Determine marker and color based on type
    marker_map = {
        "default": ("arrowhead", ds.COLORS["arrow_default"]),
        "critical": ("arrowhead-critical", ds.COLORS["arrow_blocked"]),
        "dependency": ("arrowhead-dependency", ds.COLORS["arrow_depends"]),
    }
    marker, default_color = marker_map.get(arrow_type, marker_map["default"])
    stroke = stroke or default_color

    if curve and abs(x2 - x1) > 50:
        # Create bezier curve
        mid_x = (x1 + x2) / 2
        control_offset = abs(y2 - y1) * 0.3
        control_y = min(y1, y2) - control_offset

        path = f"M{x1},{y1} Q{mid_x},{control_y} {x2},{y2}"
        return (
            f'<path d="{path}" fill="none" stroke="{stroke}" '
            f'stroke-width="{width}" marker-end="url(#{marker})"/>'
        )
    else:
        # Straight line
        return create_line(
            x1, y1, x2, y2, stroke=stroke, width=width, marker_end=marker
        )


def create_path(
    d: str,
    fill: str = "none",
    stroke: Optional[str] = None,
    stroke_width: int = 2,
    opacity: float = 1.0,
) -> str:
    """Create a path element."""
    stroke_attr = f'stroke="{stroke}"' if stroke else ""
    return (
        f'<path d="{d}" fill="{fill}" {stroke_attr} '
        f'stroke-width="{stroke_width}" opacity="{opacity}"/>'
    )


# ============================================================================
# COMPOSITE ELEMENTS (HIGH-LEVEL)
# ============================================================================


def create_node_box(
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    subtitle: Optional[str] = None,
    badge: Optional[str] = None,
    color: Optional[str] = None,
    border_color: Optional[str] = None,
) -> str:
    """
    Create a node box with title, optional subtitle, and badge.

    Args:
        x, y: Position
        width, height: Dimensions
        title: Main title text
        subtitle: Optional subtitle
        badge: Optional badge text (e.g., count)
        color: Fill color
        border_color: Border color

    Returns:
        SVG group containing box and text
    """
    ds = DesignSystem
    color = color or ds.COLORS["bg_secondary"]
    border_color = border_color or ds.COLORS["border"]

    parts = ["<g>"]

    # Background box
    parts.append(
        create_rect(x, y, width, height, fill=color, stroke=border_color, shadow=True)
    )

    # Title
    title_y = y + height / 2 if not subtitle else y + height / 2 - 6
    parts.append(
        create_text(
            x + width / 2,
            title_y,
            title,
            size=ds.FONTS["size_body"],
            anchor="middle",
            weight="bold",
            truncate_at=20,
        )
    )

    # Subtitle
    if subtitle:
        parts.append(
            create_text(
                x + width / 2,
                y + height / 2 + 10,
                subtitle,
                size=ds.FONTS["size_small"],
                fill=ds.COLORS["text_secondary"],
                anchor="middle",
                truncate_at=25,
            )
        )

    # Badge
    if badge:
        badge_x = x + width - 20
        badge_y = y + 15
        parts.append(
            create_circle(
                badge_x,
                badge_y,
                12,
                fill=ds.COLORS["chart_blue"],
                stroke=ds.COLORS["bg_primary"],
            )
        )
        parts.append(
            create_text(
                badge_x,
                badge_y + 4,
                str(badge),
                size=ds.FONTS["size_tiny"],
                fill=ds.COLORS["text_inverse"],
                anchor="middle",
                weight="bold",
            )
        )

    parts.append("</g>")
    return "\n".join(parts)


def create_legend(
    x: float, y: float, items: List[Tuple[str, str]], title: str = "Legend"
) -> str:
    """
    Create a legend box with colored indicators and labels.

    Args:
        x, y: Position
        items: List of (label, color) tuples
        title: Legend title

    Returns:
        SVG group containing legend
    """
    ds = DesignSystem
    width = ds.LAYOUT["chart_legend_width"]
    height = 30 + (len(items) * 25)

    parts = ["<g>"]

    # Background
    parts.append(
        create_rect(
            x,
            y,
            width,
            height,
            fill=ds.COLORS["bg_primary"],
            stroke=ds.COLORS["border"],
        )
    )

    # Title
    parts.append(
        create_text(x + 10, y + 20, title, size=ds.FONTS["size_small"], weight="bold")
    )

    # Items
    for i, (label, color) in enumerate(items):
        item_y = y + 40 + (i * 25)

        # Color indicator
        parts.append(
            create_rect(
                x + 10,
                item_y - 8,
                16,
                16,
                fill=color,
                stroke=ds.COLORS["border"],
                radius=3,
            )
        )

        # Label
        parts.append(
            create_text(
                x + 32, item_y + 4, label, size=ds.FONTS["size_small"], truncate_at=18
            )
        )

    parts.append("</g>")
    return "\n".join(parts)


def create_title(text: str, x: float, y: float, subtitle: Optional[str] = None) -> str:
    """
    Create diagram title with optional subtitle.

    Args:
        text: Title text
        x, y: Position
        subtitle: Optional subtitle

    Returns:
        SVG text elements
    """
    ds = DesignSystem
    parts = []

    parts.append(
        create_text(
            x, y, text, size=ds.FONTS["size_title"], anchor="middle", weight="bold"
        )
    )

    if subtitle:
        parts.append(
            create_text(
                x,
                y + 20,
                subtitle,
                size=ds.FONTS["size_small"],
                fill=ds.COLORS["text_secondary"],
                anchor="middle",
            )
        )

    return "\n".join(parts)


def create_empty_state(width: int, height: int, title: str, message: str) -> str:
    """
    Create empty state diagram.

    Args:
        width: Canvas width
        height: Canvas height
        title: Empty state title
        message: Empty state message

    Returns:
        Complete SVG with empty state
    """
    ds = DesignSystem
    cx = width / 2
    cy = height / 2

    parts = [create_svg_canvas(width, height)]

    # Background
    parts.append(
        create_rect(0, 0, width, height, fill=ds.COLORS["bg_secondary"], opacity=0.5)
    )

    # Icon (large circle with question mark or info icon)
    parts.append(
        create_circle(
            cx,
            cy - 40,
            40,
            fill=ds.COLORS["bg_tertiary"],
            stroke=ds.COLORS["border"],
            stroke_width=2,
        )
    )

    parts.append(
        create_text(
            cx,
            cy - 30,
            "?",
            size=50,
            fill=ds.COLORS["text_secondary"],
            anchor="middle",
            weight="bold",
        )
    )

    # Title
    parts.append(
        create_text(
            cx,
            cy + 40,
            title,
            size=ds.FONTS["size_heading"],
            anchor="middle",
            weight="bold",
        )
    )

    # Message
    wrapped_lines = wrap_text(message, 60)
    for i, line in enumerate(wrapped_lines):
        parts.append(
            create_text(
                cx,
                cy + 65 + (i * 18),
                line,
                size=ds.FONTS["size_body"],
                fill=ds.COLORS["text_secondary"],
                anchor="middle",
            )
        )

    parts.append(close_svg())
    return "\n".join(parts)


# ============================================================================
# GRID AND AXES
# ============================================================================


def create_grid(
    x: float,
    y: float,
    width: float,
    height: float,
    x_lines: List[float],
    y_lines: List[float],
) -> str:
    """
    Create grid lines for charts.

    Args:
        x, y: Grid origin
        width, height: Grid dimensions
        x_lines: X positions for vertical lines
        y_lines: Y positions for horizontal lines

    Returns:
        SVG group with grid lines
    """
    ds = DesignSystem
    parts = ['<g class="grid">']

    # Vertical lines
    for x_pos in x_lines:
        parts.append(
            create_line(
                x + x_pos,
                y,
                x + x_pos,
                y + height,
                stroke=ds.COLORS["grid_line"],
                width=1,
                dashed=True,
            )
        )

    # Horizontal lines
    for y_pos in y_lines:
        parts.append(
            create_line(
                x,
                y + y_pos,
                x + width,
                y + y_pos,
                stroke=ds.COLORS["grid_line"],
                width=1,
                dashed=True,
            )
        )

    parts.append("</g>")
    return "\n".join(parts)


def create_axes(
    x: float,
    y: float,
    width: float,
    height: float,
    x_labels: List[str],
    y_labels: List[str],
    x_title: str = "",
    y_title: str = "",
) -> str:
    """
    Create X and Y axes with labels.

    Args:
        x, y: Origin
        width, height: Dimensions
        x_labels: X-axis labels
        y_labels: Y-axis labels
        x_title: X-axis title
        y_title: Y-axis title

    Returns:
        SVG group with axes
    """
    ds = DesignSystem
    parts = ['<g class="axes">']

    # X-axis line
    parts.append(
        create_line(
            x,
            y + height,
            x + width,
            y + height,
            stroke=ds.COLORS["text_primary"],
            width=2,
        )
    )

    # Y-axis line
    parts.append(
        create_line(x, y, x, y + height, stroke=ds.COLORS["text_primary"], width=2)
    )

    # X-axis labels
    if x_labels:
        label_spacing = width / max(len(x_labels) - 1, 1) if len(x_labels) > 1 else 0
        for i, label in enumerate(x_labels):
            label_x = x + (i * label_spacing) if len(x_labels) > 1 else x + width / 2
            parts.append(
                create_text(
                    label_x,
                    y + height + 20,
                    label,
                    size=ds.FONTS["size_small"],
                    anchor="middle",
                    truncate_at=15,
                )
            )

    # Y-axis labels
    if y_labels:
        label_spacing = height / max(len(y_labels) - 1, 1) if len(y_labels) > 1 else 0
        for i, label in enumerate(y_labels):
            label_y = (
                y + height - (i * label_spacing)
                if len(y_labels) > 1
                else y + height / 2
            )
            parts.append(
                create_text(
                    x - 10,
                    label_y + 4,
                    str(label),
                    size=ds.FONTS["size_small"],
                    anchor="end",
                )
            )

    # Axis titles
    if x_title:
        parts.append(
            create_text(
                x + width / 2,
                y + height + 45,
                x_title,
                size=ds.FONTS["size_body"],
                anchor="middle",
                weight="bold",
            )
        )

    if y_title:
        # Rotated text for Y-axis (using transform)
        parts.append(
            f'<text x="{x - 40}" y="{y + height / 2}" '
            f'font-size="{ds.FONTS["size_body"]}" '
            f'text-anchor="middle" font-weight="bold" '
            f'transform="rotate(-90 {x - 40} {y + height / 2})">{escape_svg_text(y_title)}</text>'
        )

    parts.append("</g>")
    return "\n".join(parts)
