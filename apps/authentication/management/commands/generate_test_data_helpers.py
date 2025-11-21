"""
Helper functions and data templates for comprehensive test data generation.
"""

PROJECT_TEMPLATES = [
    {
        'name': 'E-Commerce Platform',
        'key': 'ECOM',
        'description': 'Next-generation e-commerce platform with AI-powered recommendations',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Healthcare Portal',
        'key': 'HLTH',
        'description': 'Patient management and telemedicine platform',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'critical',
    },
    {
        'name': 'Financial Dashboard',
        'key': 'FIN',
        'description': 'Real-time financial analytics and reporting system',
        'methodology': 'kanban',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Education Platform',
        'key': 'EDU',
        'description': 'Online learning management system with video streaming',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'Mobile Banking App',
        'key': 'BANK',
        'description': 'Secure mobile banking application with biometric authentication',
        'methodology': 'scrum',
        'status': 'planning',
        'priority': 'critical',
    },
    {
        'name': 'IoT Monitoring System',
        'key': 'IOT',
        'description': 'Real-time monitoring for IoT devices and sensors',
        'methodology': 'kanban',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'Social Network Platform',
        'key': 'SOCIAL',
        'description': 'Professional networking platform with AI matching',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Inventory Management',
        'key': 'INV',
        'description': 'Cloud-based inventory tracking and warehouse management',
        'methodology': 'kanban',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'CRM System',
        'key': 'CRM',
        'description': 'Customer relationship management with sales pipeline tracking',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Analytics Engine',
        'key': 'ANLYT',
        'description': 'Big data analytics platform with machine learning capabilities',
        'methodology': 'scrum',
        'status': 'planning',
        'priority': 'high',
    },
    {
        'name': 'Logistics Platform',
        'key': 'LOG',
        'description': 'Supply chain and logistics management system',
        'methodology': 'kanban',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'HR Management System',
        'key': 'HR',
        'description': 'Human resources management with recruitment automation',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'Real Estate Portal',
        'key': 'REAL',
        'description': 'Property listing and virtual tour platform',
        'methodology': 'kanban',
        'status': 'planning',
        'priority': 'low',
    },
    {
        'name': 'Booking System',
        'key': 'BOOK',
        'description': 'Multi-service booking and reservation platform',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Content Management',
        'key': 'CMS',
        'description': 'Headless CMS with multi-channel publishing',
        'methodology': 'kanban',
        'status': 'completed',
        'priority': 'medium',
    },
    {
        'name': 'Video Streaming Service',
        'key': 'VIDEO',
        'description': 'Live and on-demand video streaming platform',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
    {
        'name': 'Food Delivery App',
        'key': 'FOOD',
        'description': 'Restaurant ordering and delivery tracking system',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'Fitness Tracker',
        'key': 'FIT',
        'description': 'Health and fitness tracking with workout plans',
        'methodology': 'kanban',
        'status': 'planning',
        'priority': 'low',
    },
    {
        'name': 'Travel Booking',
        'key': 'TRVL',
        'description': 'Comprehensive travel booking and itinerary management',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'medium',
    },
    {
        'name': 'Project Management Tool',
        'key': 'PM',
        'description': 'Agile project management with advanced reporting',
        'methodology': 'scrum',
        'status': 'active',
        'priority': 'high',
    },
]

ISSUE_TYPE_TEMPLATES = [
    {'name': 'Epic', 'category': 'epic', 'icon': '🎯', 'color': '#6554C0'},
    {'name': 'Story', 'category': 'story', 'icon': '📖', 'color': '#00875A'},
    {'name': 'Task', 'category': 'task', 'icon': '✓', 'color': '#0052CC'},
    {'name': 'Bug', 'category': 'bug', 'icon': '🐛', 'color': '#DE350B'},
    {'name': 'Improvement', 'category': 'improvement', 'icon': '⚡', 'color': '#FF991F'},
    {'name': 'Sub-task', 'category': 'sub_task', 'icon': '📋', 'color': '#5E6C84'},
]

WORKFLOW_STATUS_TEMPLATES = [
    {'name': 'To Do', 'category': 'to_do', 'color': '#DFE1E6', 'order': 0, 'is_initial': True},
    {'name': 'In Progress', 'category': 'in_progress', 'color': '#0052CC', 'order': 1},
    {'name': 'In Review', 'category': 'in_progress', 'color': '#FF991F', 'order': 2},
    {'name': 'Done', 'category': 'done', 'color': '#00875A', 'order': 3, 'is_final': True},
]

# Issue title templates
STORY_TEMPLATES = [
    "As a user, I want to {action} so that I can {benefit}",
    "User should be able to {action}",
    "Implement {feature} functionality",
    "Add {feature} to {area}",
    "Support for {feature}",
]

TASK_TEMPLATES = [
    "Setup {component} configuration",
    "Implement {technical_item}",
    "Configure {service} integration",
    "Create {database_item} schema",
    "Optimize {performance_item}",
]

BUG_TEMPLATES = [
    "Fix {problem} in {area}",
    "{Problem} when {condition}",
    "{Area} not working correctly",
    "Error in {component}: {error_type}",
    "Resolve {issue_type} issue",
]

EPIC_TEMPLATES = [
    "{feature} Module Development",
    "{feature} System Implementation",
    "{feature} Platform Features",
    "{feature} Feature Set",
]

# Word banks for generating titles
ACTIONS = ['login', 'register', 'search', 'filter', 'export', 'import', 'edit', 'delete', 'share', 'download', 'upload', 'view', 'create', 'update']
BENEFITS = ['improve usability', 'save time', 'increase productivity', 'better organization', 'easier access', 'reduce errors', 'enhance security']
FEATURES = ['authentication', 'dashboard', 'reporting', 'notifications', 'settings', 'profile', 'analytics', 'billing', 'messaging', 'calendar']
AREAS = ['homepage', 'user profile', 'admin panel', 'settings page', 'dashboard', 'reports section', 'navigation menu', 'sidebar']
COMPONENTS = ['database', 'API', 'frontend', 'backend', 'cache', 'queue', 'websocket', 'server', 'client']
PROBLEMS = ['crash', 'slow performance', 'memory leak', 'incorrect data', 'UI glitch', 'validation error', 'timeout', 'data loss']

# Comment templates
COMMENT_TEMPLATES = [
    "This is looking good. Let's move forward with this approach.",
    "I have some concerns about the implementation. Can we discuss?",
    "Updated the design based on feedback.",
    "Testing completed successfully.",
    "Found an edge case that needs to be addressed.",
    "This is blocked by {dependency}. We need to resolve that first.",
    "Great work on this! Just a few minor suggestions.",
    "I've reviewed the code and it looks solid.",
    "We should consider the performance implications here.",
    "Documentation has been updated to reflect these changes.",
    "Can you provide more details on the requirements?",
    "I'll take care of this one.",
    "Moving this to the next sprint due to priority changes.",
    "This is ready for review.",
    "Merged to main branch.",
]
