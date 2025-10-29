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
        'todo': '#6C757D',           # Neutral gray
        'in_progress': '#0052CC',    # Professional blue
        'done': '#00875A',           # Success green
        'backlog': '#6C757D',        # Same as todo
        'blocked': '#DE350B',        # Alert red
        'code_review': '#5243AA',    # Review purple
        'testing': '#FF991F',        # Testing orange
        
        # Status Categories (Alternative naming)
        'status_todo': '#6C757D',
        'status_in_progress': '#0052CC',
        'status_done': '#00875A',
        'status_blocked': '#DE350B',
        
        # Priority Colors
        'priority_p0': '#DE350B',    # Highest
        'priority_p1': '#FF991F',    # High
        'priority_p2': '#0052CC',    # Medium
        'priority_p3': '#6C757D',    # Low
        'priority_p4': '#97A0AF',    # Lowest
        
        # UI Colors
        'bg_primary': '#FFFFFF',     # White
        'bg_secondary': '#FAFBFC',   # Off-white
        'bg_tertiary': '#F4F5F7',    # Light gray
        'border': '#DFE1E6',         # Light border
        'border_strong': '#42526E',  # Strong border
        
        # Text Colors
        'text_primary': '#172B4D',   # Dark blue-gray
        'text_secondary': '#5E6C84', # Muted gray
        'text_tertiary': '#8993A4',  # Light gray
        'text_inverse': '#FFFFFF',   # White on dark bg
        
        # Chart Colors (for data visualization)
        'chart_blue': '#0052CC',
        'chart_green': '#00875A',
        'chart_orange': '#FF991F',
        'chart_red': '#DE350B',
        'chart_purple': '#5243AA',
        'chart_teal': '#00B8D9',
        'chart_yellow': '#FFAB00',
        'chart_pink': '#E774BB',
        
        # Utility Colors
        'grid_line': '#E9ECEF',      # Grid lines in charts
        'today_marker': '#DE350B',   # Today indicator
        'critical_path': '#DE350B',  # Critical path highlighting
        'ideal_line': '#8993A4',     # Ideal burndown line
        'actual_line': '#0052CC',    # Actual progress line
        
        # Connection/Arrow Colors
        'arrow_default': '#42526E',  # Default arrow color
        'arrow_blocked': '#DE350B',  # Blocking relationship
        'arrow_depends': '#0052CC',  # Dependency relationship
        
        # Shadows
        'shadow': 'rgba(9, 30, 66, 0.08)',  # Subtle shadow
    }
    
    # ========================================================================
    # TYPOGRAPHY
    # ========================================================================
    
    FONTS: Dict[str, any] = {
        'family': "'Arial', 'Helvetica', sans-serif",
        'family_mono': "'Courier New', 'Courier', monospace",
        
        # Font Sizes (px)
        'size_title': 18,      # Main diagram title
        'size_heading': 14,    # Section headings
        'size_body': 12,       # Primary text
        'size_small': 10,      # Secondary text
        'size_tiny': 9,        # Metadata
        
        # Font Weights
        'weight_regular': 'normal',
        'weight_medium': '500',
        'weight_bold': 'bold',
        
        # Line Heights
        'line_height_tight': 1.2,
        'line_height_normal': 1.5,
        'line_height_loose': 1.8,
    }
    
    # ========================================================================
    # SPACING - 8px Grid System
    # ========================================================================
    
    SPACING: Dict[str, int] = {
        'xxs': 4,      # 0.5 unit
        'xs': 8,       # 1 unit
        'sm': 12,      # 1.5 units
        'md': 16,      # 2 units
        'lg': 24,      # 3 units
        'xl': 32,      # 4 units
        'xxl': 40,     # 5 units
        'xxxl': 48,    # 6 units
    }
    
    # ========================================================================
    # SHAPE PROPERTIES
    # ========================================================================
    
    SHAPES: Dict[str, any] = {
        # Border Radius
        'radius_sm': 3,
        'radius_md': 6,
        'radius_lg': 8,
        'radius_xl': 12,
        
        # Border Widths
        'border_thin': 1,
        'border_normal': 2,
        'border_thick': 3,
        
        # Arrow Properties
        'arrow_size': 8,
        'arrow_width': 2,
        
        # Node Sizes
        'node_min_width': 120,
        'node_min_height': 60,
        'node_padding_x': 12,
        'node_padding_y': 8,
        
        # Shadow
        'shadow_blur': 3,
        'shadow_offset_x': 0,
        'shadow_offset_y': 2,
        'shadow_opacity': 0.15,
    }
    
    # ========================================================================
    # LAYOUT CONSTANTS
    # ========================================================================
    
    LAYOUT: Dict[str, int] = {
        # Canvas
        'canvas_padding': 40,
        'canvas_min_width': 800,
        'canvas_min_height': 600,
        
        # Node Spacing
        'node_spacing_x': 200,    # Horizontal gap between nodes
        'node_spacing_y': 120,    # Vertical gap between nodes
        
        # Workflow Diagram
        'workflow_node_width': 160,
        'workflow_node_height': 80,
        'workflow_spacing_x': 220,
        
        # Dependency Graph
        'dependency_node_width': 180,
        'dependency_node_height': 70,
        'dependency_spacing_x': 220,
        'dependency_spacing_y': 100,
        
        # Charts
        'chart_margin_top': 60,
        'chart_margin_right': 60,
        'chart_margin_bottom': 60,
        'chart_margin_left': 60,
        'chart_legend_width': 180,
        'chart_axis_label_space': 40,
        
        # Roadmap
        'roadmap_row_height': 50,
        'roadmap_bar_height': 30,
        'roadmap_milestone_size': 12,
        
        # Grid
        'grid_spacing': 50,  # Grid line spacing for charts
    }
    
    # ========================================================================
    # CHART CONSTANTS
    # ========================================================================
    
    CHART: Dict[str, any] = {
        # Line Chart
        'line_width': 2,
        'point_radius': 4,
        'point_radius_hover': 6,
        
        # Bar Chart
        'bar_spacing': 10,
        'bar_min_width': 30,
        'bar_max_width': 60,
        
        # Area Chart
        'area_opacity': 0.7,
        'area_stroke_width': 2,
        
        # Grid
        'grid_line_width': 1,
        'grid_line_dash': '2,4',
        
        # Axis
        'axis_line_width': 2,
        'tick_length': 6,
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
        key = f'status_{status_category}' if not status_category.startswith('status_') else status_category
        return cls.COLORS.get(key, cls.COLORS.get(status_category, cls.COLORS['text_secondary']))
    
    @classmethod
    def get_priority_color(cls, priority: str) -> str:
        """
        Get color for priority level.
        
        Args:
            priority: Priority level (P0, P1, P2, P3, P4)
            
        Returns:
            Hex color code
        """
        key = f'priority_{priority.lower()}'
        return cls.COLORS.get(key, cls.COLORS['text_secondary'])
    
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
            cls.COLORS['chart_blue'],
            cls.COLORS['chart_green'],
            cls.COLORS['chart_orange'],
            cls.COLORS['chart_purple'],
            cls.COLORS['chart_teal'],
            cls.COLORS['chart_red'],
            cls.COLORS['chart_yellow'],
            cls.COLORS['chart_pink'],
        ]
        return chart_colors[index % len(chart_colors)]


# ============================================================================
# TEXT UTILITIES
# ============================================================================

def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
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
    return text[:max_length - len(suffix)] + suffix


def escape_svg_text(text: str) -> str:
    """
    Escape special characters for safe use in SVG text elements.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for SVG
    """
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
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
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_length
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines[:3]  # Limit to 3 lines max


# ============================================================================
# LAYOUT UTILITIES
# ============================================================================

def calculate_canvas_size(num_items: int, item_width: int, item_spacing: int, 
                         items_per_row: int, padding: int = 40) -> tuple:
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
    width = (items_per_row * item_width) + ((items_per_row - 1) * item_spacing) + (padding * 2)
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
