"""
Design System Constants for Professional SVG Diagrams.

Provides consistent color palette, typography, spacing, and shape constants
following WCAG AA accessibility standards and modern UX/UI principles.
"""

from typing import Dict


class DesignSystem:
    """
    Professional design system for consistent, accessible diagrams.

    All colors meet WCAG AA contrast requirements.
    All spacing follows 8px grid system for visual rhythm.
    """

    # ========================================================================
    # COLOR PALETTE - WCAG AA Compliant
    # ========================================================================

    COLORS: Dict[str, str] = {
        # Status Colors (Primary)
        "todo": "#6C757D",  # Neutral gray
        "in_progress": "#0052CC",  # Professional blue
        "done": "#00875A",  # Success green
        "backlog": "#6C757D",  # Same as todo
        "blocked": "#DE350B",  # Alert red
        "code_review": "#5243AA",  # Review purple
        "testing": "#FF991F",  # Testing orange
        # Status Categories (Alternative naming)
        "status_todo": "#6C757D",
        "status_in_progress": "#0052CC",
        "status_done": "#00875A",
        "status_blocked": "#DE350B",
        # Priority Colors
        "priority_p0": "#DE350B",  # Highest
        "priority_p1": "#FF991F",  # High
        "priority_p2": "#0052CC",  # Medium
        "priority_p3": "#6C757D",  # Low
        "priority_p4": "#97A0AF",  # Lowest
        # UI Colors
        "bg_primary": "#FFFFFF",  # White
        "bg_secondary": "#FAFBFC",  # Off-white
        "bg_tertiary": "#F4F5F7",  # Light gray
        "border": "#DFE1E6",  # Light border
        "border_strong": "#42526E",  # Strong border
        # Text Colors
        "text_primary": "#172B4D",  # Dark blue-gray
        "text_secondary": "#5E6C84",  # Muted gray
        "text_tertiary": "#8993A4",  # Light gray
        "text_inverse": "#FFFFFF",  # White on dark bg
        # Chart Colors (for data visualization)
        "chart_blue": "#0052CC",
        "chart_green": "#00875A",
        "chart_orange": "#FF991F",
        "chart_red": "#DE350B",
        "chart_purple": "#5243AA",
        "chart_teal": "#00B8D9",
        "chart_yellow": "#FFAB00",
        "chart_pink": "#E774BB",
        # Status Category Colors (vibrant colors for workflow)
        "status_todo": "#5E6C84",  # Gray for backlog/todo
        "status_backlog": "#5E6C84",  # Gray for backlog
        "status_in_progress": "#0052CC",  # Vibrant blue for in progress
        "status_in_review": "#0052CC",  # Blue for review
        "status_done": "#00875A",  # Vibrant green for done
        "status_blocked": "#DE350B",  # Red for blocked
        "status_cancelled": "#8993A4",  # Light gray for cancelled
        # Workflow-specific colors (aliases)
        "todo": "#5E6C84",
        "in_progress": "#0052CC",
        "done": "#00875A",
        "blocked": "#DE350B",
        # Priority Colors
        "priority_p0": "#DE350B",  # Critical - Red
        "priority_p1": "#FF991F",  # High - Orange
        "priority_p2": "#0052CC",  # Medium - Blue
        "priority_p3": "#5E6C84",  # Low - Gray
        "priority_p4": "#8993A4",  # Lowest - Light Gray
        # Utility Colors
        "grid_line": "#E9ECEF",  # Grid lines in charts
        "today_marker": "#DE350B",  # Today indicator
        "critical_path": "#DE350B",  # Critical path highlighting
        "ideal_line": "#8993A4",  # Ideal burndown line
        "actual_line": "#0052CC",  # Actual progress line
        # Connection/Arrow Colors
        "arrow_default": "#42526E",  # Default arrow color
        "arrow_blocked": "#DE350B",  # Blocking relationship
        "arrow_depends": "#0052CC",  # Dependency relationship
        # Shadows
        "shadow": "rgba(9, 30, 66, 0.08)",  # Subtle shadow
    }

    # ========================================================================
    # TYPOGRAPHY
    # ========================================================================

    FONTS: Dict[str, any] = {
        "family": "'Arial', 'Helvetica', sans-serif",
        "family_mono": "'Courier New', 'Courier', monospace",
        # Font Sizes (px) - INCREASED for better visibility
        "size_title": 20,  # Main diagram title (was 18)
        "size_heading": 16,  # Section headings (was 14)
        "size_body": 14,  # Primary text (was 12)
        "size_small": 12,  # Secondary text (was 10)
        "size_tiny": 11,  # Metadata (was 9)
        # Font Weights
        "weight_regular": "normal",
        "weight_medium": "500",
        "weight_bold": "bold",
        # Line Heights
        "line_height_tight": 1.2,
        "line_height_normal": 1.5,
        "line_height_loose": 1.8,
    }

    # ========================================================================
    # SPACING - 8px Grid System
    # ========================================================================

    SPACING: Dict[str, int] = {
        "xxs": 4,  # 0.5 unit
        "xs": 8,  # 1 unit
        "sm": 12,  # 1.5 units
        "md": 16,  # 2 units
        "lg": 24,  # 3 units
        "xl": 32,  # 4 units
        "xxl": 40,  # 5 units
        "xxxl": 48,  # 6 units
    }

    # ========================================================================
    # SHAPE PROPERTIES
    # ========================================================================

    SHAPES: Dict[str, any] = {
        # Border Radius
        "radius_sm": 3,
        "radius_md": 6,
        "radius_lg": 8,
        "radius_xl": 12,
        # Border Widths
        "border_thin": 1,
        "border_normal": 2,
        "border_thick": 3,
        # Arrow Properties
        "arrow_size": 8,
        "arrow_width": 2,
        # Node Sizes
        "node_min_width": 120,
        "node_min_height": 60,
        "node_padding_x": 12,
        "node_padding_y": 8,
        # Shadow
        "shadow_blur": 3,
        "shadow_offset_x": 0,
        "shadow_offset_y": 2,
        "shadow_opacity": 0.15,
    }

    # ========================================================================
    # LAYOUT CONSTANTS
    # ========================================================================

    LAYOUT: Dict[str, int] = {
        # Canvas - INCREASED minimum dimensions
        "canvas_padding": 60,
        "canvas_min_width": 1600,  # Was 1000, increased for better visibility
        "canvas_min_height": 500,  # Was 700, adjusted
        # Node Spacing
        "node_spacing_x": 250,  # Horizontal gap between nodes - INCREASED
        "node_spacing_y": 150,  # Vertical gap between nodes - INCREASED
        # Workflow Diagram - IMPROVED DIMENSIONS
        "workflow_node_width": 220,  # Increased from 200 for better text fit
        "workflow_node_height": 100,  # Increased from 80
        "workflow_spacing_x": 300,  # Increased from 280 for label space
        # Dependency Graph - IMPROVED DIMENSIONS
        "dependency_node_width": 220,  # Increased from 180
        "dependency_node_height": 100,  # Increased from 90 for better text
        "dependency_spacing_x": 280,  # Increased from 260 for more breathing room
        "dependency_spacing_y": 140,  # Increased from 130
        # Charts
        "chart_margin_top": 60,
        "chart_margin_right": 60,
        "chart_margin_bottom": 60,
        "chart_margin_left": 60,
        "chart_legend_width": 200,
        "chart_axis_label_space": 40,
        # Roadmap - IMPROVED DIMENSIONS
        "roadmap_row_height": 70,  # Increased from 50
        "roadmap_bar_height": 45,  # Increased from 30
        "roadmap_milestone_size": 12,
        "roadmap_label_width": 220,  # NEW: Space for sprint names
        "roadmap_min_width": 1800,  # NEW: Minimum width for timeline
        "roadmap_min_height": 600,  # NEW: Minimum height
        # Grid
        "grid_spacing": 50,  # Grid line spacing for charts
    }

    # ========================================================================
    # CHART CONSTANTS
    # ========================================================================

    CHART: Dict[str, any] = {
        # Line Chart
        "line_width": 2,
        "point_radius": 4,
        "point_radius_hover": 6,
        # Bar Chart
        "bar_spacing": 10,
        "bar_min_width": 30,
        "bar_max_width": 60,
        # Area Chart
        "area_opacity": 0.7,
        "area_stroke_width": 2,
        # Grid
        "grid_line_width": 1,
        "grid_line_dash": "2,4",
        # Axis
        "axis_line_width": 2,
        "tick_length": 6,
    }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @classmethod
    def get_status_color(cls, status_category: str) -> str:
        """
        Get color for status category.

        Args:
            status_category: Status category (todo, in_progress, done, etc.)

        Returns:
            Hex color code
        """
        key = (
            f"status_{status_category}"
            if not status_category.startswith("status_")
            else status_category
        )
        return cls.COLORS.get(
            key, cls.COLORS.get(status_category, cls.COLORS["text_secondary"])
        )

    @classmethod
    def get_priority_color(cls, priority: str) -> str:
        """
        Get color for priority level.

        Args:
            priority: Priority level (P0, P1, P2, P3, P4)

        Returns:
            Hex color code
        """
        key = f"priority_{priority.lower()}"
        return cls.COLORS.get(key, cls.COLORS["text_secondary"])

    @classmethod
    def get_chart_color(cls, index: int) -> str:
        """
        Get chart color from palette by index (cycles through colors).

        Args:
            index: Color index

        Returns:
            Hex color code
        """
        chart_colors = [
            cls.COLORS["chart_blue"],
            cls.COLORS["chart_green"],
            cls.COLORS["chart_orange"],
            cls.COLORS["chart_purple"],
            cls.COLORS["chart_teal"],
            cls.COLORS["chart_red"],
            cls.COLORS["chart_yellow"],
            cls.COLORS["chart_pink"],
        ]
        return chart_colors[index % len(chart_colors)]


# ============================================================================
# TEXT UTILITIES
# ============================================================================


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def escape_svg_text(text: str) -> str:
    """
    Escape special characters for safe use in SVG text elements.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for SVG
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def wrap_text(text: str, max_chars_per_line: int) -> list:
    """
    Wrap text into multiple lines based on character limit.

    Args:
        text: Text to wrap
        max_chars_per_line: Maximum characters per line

    Returns:
        List of text lines
    """
    if len(text) <= max_chars_per_line:
        return [text]

    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        # +1 for space
        if current_length + word_length + len(current_line) <= max_chars_per_line:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    return lines[:3]  # Limit to 3 lines max


# ============================================================================
# LAYOUT UTILITIES
# ============================================================================


def calculate_canvas_size(
    num_items: int,
    item_width: int,
    item_spacing: int,
    items_per_row: int,
    padding: int = 40,
) -> tuple:
    """
    Calculate optimal canvas dimensions based on number of items.

    Args:
        num_items: Number of items to display
        item_width: Width of each item
        item_spacing: Spacing between items
        items_per_row: Maximum items per row
        padding: Canvas padding

    Returns:
        Tuple of (width, height)
    """
    rows = (num_items + items_per_row - 1) // items_per_row
    width = (
        (items_per_row * item_width)
        + ((items_per_row - 1) * item_spacing)
        + (padding * 2)
    )
    height = (rows * 100) + (padding * 2)  # Approximate height

    return max(width, 800), max(height, 600)


def calculate_grid_points(min_val: float, max_val: float, num_lines: int = 5) -> list:
    """
    Calculate nice grid points for chart axes.

    Args:
        min_val: Minimum value
        max_val: Maximum value
        num_lines: Desired number of grid lines

    Returns:
        List of grid point values
    """
    if max_val == min_val:
        return [min_val]

    range_val = max_val - min_val
    step = range_val / num_lines

    # Round to nice numbers
    magnitude = 10 ** (len(str(int(step))) - 1)
    nice_step = round(step / magnitude) * magnitude

    if nice_step == 0:
        nice_step = 1

    points = []
    current = (min_val // nice_step) * nice_step
    while current <= max_val:
        points.append(current)
        current += nice_step

    return points if points else [min_val, max_val]


# ============================================================================
# TEXT MEASUREMENT AND COLLISION DETECTION
# ============================================================================


def estimate_text_width(text: str, font_size: int, font_family: str = "Arial") -> float:
    """
    Estimate text width in pixels for SVG rendering.

    Uses character-based approximation since server-side SVG generation
    cannot access browser text measurement APIs.

    Args:
        text: Text string to measure
        font_size: Font size in pixels
        font_family: Font family (affects character width)

    Returns:
        Estimated width in pixels (includes 20% safety buffer)
    """
    if not text:
        return 0

    # Character width multipliers (proportion of font_size)
    char_widths = {
        # Narrow characters
        "i": 0.3,
        "l": 0.3,
        "t": 0.35,
        "I": 0.3,
        "j": 0.3,
        "f": 0.35,
        # Medium characters (most lowercase)
        "a": 0.55,
        "b": 0.55,
        "c": 0.5,
        "d": 0.55,
        "e": 0.55,
        "g": 0.55,
        "h": 0.55,
        "k": 0.5,
        "n": 0.55,
        "o": 0.55,
        "p": 0.55,
        "q": 0.55,
        "r": 0.35,
        "s": 0.5,
        "u": 0.55,
        "v": 0.5,
        "x": 0.5,
        "y": 0.5,
        "z": 0.5,
        # Wide characters
        "m": 0.85,
        "w": 0.75,
        # Uppercase (generally wider)
        "A": 0.65,
        "B": 0.65,
        "C": 0.65,
        "D": 0.65,
        "E": 0.6,
        "F": 0.55,
        "G": 0.7,
        "H": 0.65,
        "J": 0.5,
        "K": 0.65,
        "L": 0.55,
        "M": 0.8,
        "N": 0.65,
        "O": 0.7,
        "P": 0.6,
        "Q": 0.7,
        "R": 0.65,
        "S": 0.6,
        "T": 0.6,
        "U": 0.65,
        "V": 0.65,
        "W": 0.9,
        "X": 0.65,
        "Y": 0.6,
        "Z": 0.6,
        # Numbers
        "0": 0.55,
        "1": 0.4,
        "2": 0.55,
        "3": 0.55,
        "4": 0.55,
        "5": 0.55,
        "6": 0.55,
        "7": 0.5,
        "8": 0.55,
        "9": 0.55,
        # Common punctuation
        " ": 0.3,
        ".": 0.3,
        ",": 0.3,
        ":": 0.3,
        ";": 0.3,
        "-": 0.35,
        "_": 0.5,
        "(": 0.35,
        ")": 0.35,
    }

    # Default width for characters not in map
    default_width = 0.55

    total_width = 0
    for char in text:
        char_width = char_widths.get(char, default_width)
        total_width += char_width * font_size

    # Add 20% safety buffer for approximation errors
    return total_width * 1.2


def estimate_text_height(font_size: int, line_height: float = 1.2) -> float:
    """
    Estimate text height including line height.

    Args:
        font_size: Font size in pixels
        line_height: Line height multiplier

    Returns:
        Estimated height in pixels
    """
    return font_size * line_height


class BoundingBox:
    """Represents a rectangular bounding box for collision detection."""

    def __init__(
        self, x: float, y: float, width: float, height: float, label: str = ""
    ):
        """
        Initialize bounding box.

        Args:
            x: Left edge X coordinate
            y: Top edge Y coordinate
            width: Box width
            height: Box height
            label: Optional label for debugging
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def overlaps(self, other: "BoundingBox", margin: float = 0) -> bool:
        """
        Check if this box overlaps with another box.

        Args:
            other: Another bounding box
            margin: Additional margin to consider (for spacing)

        Returns:
            True if boxes overlap (with margin)
        """
        return not (
            self.right + margin < other.left
            or self.left - margin > other.right
            or self.bottom + margin < other.top
            or self.top - margin > other.bottom
        )

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside this box."""
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def __repr__(self) -> str:
        return f"BoundingBox({self.label}: x={self.x:.1f}, y={self.y:.1f}, w={self.width:.1f}, h={self.height:.1f})"


def find_non_overlapping_position(
    desired_x: float,
    desired_y: float,
    width: float,
    height: float,
    existing_boxes: list,
    margin: float = 8,
    max_attempts: int = 20,
) -> tuple:
    """
    Find a position that doesn't overlap with existing bounding boxes.

    Tries moving vertically first, then horizontally if needed.

    Args:
        desired_x: Desired X position (center or left, depending on context)
        desired_y: Desired Y position (center or top)
        width: Element width
        height: Element height
        existing_boxes: List of BoundingBox objects already placed
        margin: Minimum spacing between elements
        max_attempts: Maximum position adjustment attempts

    Returns:
        Tuple of (x, y) for non-overlapping position, or original if can't find one
    """
    # Try the desired position first
    test_box = BoundingBox(desired_x - width / 2, desired_y - height / 2, width, height)

    if not any(test_box.overlaps(box, margin) for box in existing_boxes):
        return (desired_x, desired_y)

    # Try moving vertically (up then down)
    vertical_offsets = []
    for i in range(1, max_attempts // 2):
        vertical_offsets.extend([-(i * 15), i * 15])  # Try 15px increments

    for offset_y in vertical_offsets:
        test_y = desired_y + offset_y
        test_box = BoundingBox(
            desired_x - width / 2, test_y - height / 2, width, height
        )

        if not any(test_box.overlaps(box, margin) for box in existing_boxes):
            return (desired_x, test_y)

    # Try moving horizontally if vertical didn't work
    horizontal_offsets = []
    for i in range(1, max_attempts // 2):
        horizontal_offsets.extend([-(i * 20), i * 20])  # Try 20px increments

    for offset_x in horizontal_offsets:
        test_x = desired_x + offset_x
        test_box = BoundingBox(
            test_x - width / 2, desired_y - height / 2, width, height
        )

        if not any(test_box.overlaps(box, margin) for box in existing_boxes):
            return (test_x, desired_y)

    # If all else fails, return original position
    return (desired_x, desired_y)


def create_text_bounding_box(
    x: float,
    y: float,
    text: str,
    font_size: int,
    anchor: str = "start",
    padding: float = 4,
) -> BoundingBox:
    """
    Create a bounding box for text element.

    Args:
        x: Text X position
        y: Text Y position (baseline)
        text: Text content
        font_size: Font size in pixels
        anchor: Text anchor (start, middle, end)
        padding: Additional padding around text

    Returns:
        BoundingBox for the text element
    """
    width = estimate_text_width(text, font_size) + (padding * 2)
    height = estimate_text_height(font_size) + (padding * 2)

    # Adjust X based on anchor
    if anchor == "middle":
        box_x = x - width / 2
    elif anchor == "end":
        box_x = x - width
    else:  # start
        box_x = x

    # Y is baseline, so adjust for text height
    # SVG text baseline is typically at 75% of height from top
    box_y = y - (height * 0.75)

    return BoundingBox(box_x, box_y, width, height, label=text[:20])
