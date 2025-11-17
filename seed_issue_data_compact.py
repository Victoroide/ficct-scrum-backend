"""Compact issue data - 80 realistic issues across 6 sprints"""

def get_all_issues():
    """Returns list of issues per sprint with realistic content"""
    
    # Generate issues programmatically to save space
    issues_by_sprint = []
    
    # Sprint 1: 18 issues (all Done) - Authentication & Catalog
    issues_by_sprint.append(generate_sprint_issues(1, 18, "Done", [
        ("Implement OAuth2 authentication with JWT tokens", "Story", "P2", 8, "OAuth integration with Google, Facebook, GitHub. JWT tokens, refresh tokens in Redis, CSRF protection, rate limiting."),
        ("Design product catalog database schema", "Task", "P2", 5, "Product, Category, Variant tables. PostgreSQL with full-text search, constraints, indexes. Support 2000 products."),
        ("Create product listing API with pagination", "Story", "P2", 5, "REST API with filtering, sorting, search. Response < 200ms, support 1000 req/s. Redis caching."),
        ("Build product detail page with image gallery", "Story", "P2", 8, "React components with image zoom, variants selector, reviews, specs tabs. Lighthouse > 90, WebP images."),
        ("Implement advanced search with Elasticsearch", "Story", "P2", 13, "Full-text search with fuzzy matching, synonyms, autocomplete, faceted filters. Response < 100ms."),
        ("Bug: Login fails with special characters in password", "Bug", "P1", 2, "Users with !@#$%^&* in password get 400 error. Fix URL encoding, update regex, add tests."),
        ("Create categories management interface", "Task", "P3", 3, "Django admin with tree view, drag-and-drop, bulk actions, CSV export."),
        ("Implement image upload and processing", "Task", "P2", 5, "Upload to S3, generate thumbnails, convert to WebP, async processing with Celery."),
        ("Setup API rate limiting", "Task", "P2", 3, "DRF throttling, Redis counters, HTTP 429 responses, rate limit headers."),
        ("Create user profile and account settings", "Story", "P3", 8, "Personal info, change password, 2FA, address book, order history, wishlist, payment methods."),
        ("Implement product variant selection", "Task", "P2", 5, "Handle size/color variants, price updates, stock validation, disable invalid combinations."),
        ("Build responsive product grid", "Story", "P2", 5, "4-col desktop, 2-col mobile, lazy loading, virtual scrolling, WCAG 2.1 AA."),
        ("Setup CI/CD pipeline", "Task", "P2", 5, "GitHub Actions for testing, linting, security scans, Docker builds, staging/prod deployment."),
        ("Implement product reviews and ratings", "Story", "P3", 8, "1-5 stars, text reviews, photos, verified purchase badge, moderation, helpful votes."),
        ("Create product recommendations engine", "Story", "P3", 13, "Collaborative filtering, content-based, personalized recommendations. Celery for training, Redis cache."),
        ("Implement inventory management", "Story", "P2", 8, "Real-time stock tracking, reserved stock, low stock alerts, reorder points, multiple warehouses."),
        ("Bug: Images not loading on Safari", "Bug", "P2", 2, "CORS policy blocks images on Safari 16+. Fix S3 CORS config for *.domain.com."),
        ("Add product comparison feature", "Story", "P4", 5, "Compare up to 4 products side-by-side. Specifications table, localStorage persistence."),
    ]))
    
    # Sprint 2: 21 issues (all Done) - Cart & Checkout
    issues_by_sprint.append(generate_sprint_issues(2, 21, "Done", [
        ("Design shopping cart data model and API", "Task", "P2", 3, "Cart and CartItem tables, guest cart support, max 50 items, stock validation, expiry logic."),
        ("Build shopping cart UI", "Story", "P2", 8, "Mini cart dropdown, full cart page, quantity selector, WebSocket for real-time updates, empty state."),
        ("Implement guest checkout flow", "Story", "P2", 8, "Email validation, optional account creation, address forms, shipping selection, payment, order review."),
        ("Create checkout address form with validation", "Task", "P2", 5, "Google Places autocomplete, ZIP/phone validation, saved addresses, accessibility."),
        ("Implement discount codes and promotions", "Story", "P2", 8, "Percentage/fixed/free shipping discounts. Rules engine, usage limits, admin interface, bulk generation."),
        ("Build order summary and review step", "Task", "P2", 3, "Final review of items, addresses, shipping, payment. Edit buttons, place order CTA."),
        ("Implement shipping method selection", "Story", "P2", 5, "Standard/Express/Overnight/Free shipping. Carrier API integration, weight-based pricing, delivery estimates."),
        ("Add order confirmation page and email", "Story", "P2", 5, "Confirmation page, email with receipt PDF, order tracking link, add to calendar."),
        ("Implement tax calculation", "Task", "P2", 5, "Sales tax by region, VAT, city taxes. TaxJar API integration, cache rates, tax nexus rules."),
        ("Create order management admin", "Task", "P2", 8, "Order list with filters, detail view, status management, bulk actions, email notifications."),
        ("Implement cart abandonment emails", "Story", "P3", 5, "3-email sequence: 1hr reminder, 24hr with 10% off, 48hr last chance. GDPR compliance."),
        ("Add wishlist functionality", "Story", "P3", 5, "Heart icon, wishlist page, share wishlist, price drop alerts, move to cart."),
        ("Implement saved payment methods", "Story", "P3", 5, "PCI-DSS compliant tokenization, Stripe integration, manage saved cards, CVV verification."),
        ("Bug: Cart total calculation incorrect", "Bug", "P1", 2, "Subtotal wrong with multiple items. Fix quantity variable scope in reduce function."),
        ("Implement one-click checkout", "Story", "P3", 8, "Buy Now button for logged-in users, confirmation modal, fraud detection, CVV verification."),
        ("Add estimated delivery date", "Task", "P3", 3, "Show delivery estimate on product/cart/checkout. Calculate based on processing + shipping time."),
        ("Create shipping label generation", "Task", "P2", 5, "Integration with carrier APIs for label printing, tracking numbers, batch processing."),
        ("Implement order status tracking", "Story", "P3", 5, "Track order page, status timeline, email notifications, SMS updates (optional)."),
        ("Add gift wrapping option", "Task", "P4", 3, "Gift wrap checkbox, gift message, additional fee, special packaging instructions."),
        ("Implement buy now pay later", "Story", "P3", 8, "Klarna/Afterpay integration, installment plans, credit checks, payment reminders."),
        ("Bug: Checkout fails on mobile Safari", "Bug", "P2", 2, "Payment form doesn't submit on iOS. Fix touch event handling, test on iOS devices."),
    ]))
    
    # Sprint 3: 23 issues (all Done) - Payment & Orders
    issues_by_sprint.append(generate_sprint_issues(3, 23, "Done", [
        ("Integrate Stripe payment processing", "Story", "P1", 13, "Stripe Elements for secure card input, webhooks for events, idempotency, 3D Secure support."),
        ("Implement PayPal Express Checkout", "Story", "P2", 8, "PayPal SDK integration, redirect flow, refunds, partial payments support."),
        ("Add fraud detection system", "Story", "P2", 8, "Rule-based fraud checks, velocity limits, geolocation validation, suspicious pattern detection."),
        ("Create payment retry mechanism", "Task", "P2", 5, "Retry failed payments up to 3 times, exponential backoff, notify customer, admin alerts."),
        ("Implement refund processing", "Story", "P2", 5, "Full/partial refunds, refund reasons, automatic inventory return, email notifications."),
        ("Add invoice generation", "Task", "P2", 5, "PDF invoices with company logo, itemized billing, tax breakdown, download/email options."),
        ("Create order export for accounting", "Task", "P2", 3, "CSV/Excel export with customizable fields, date range filter, scheduled exports."),
        ("Implement order status webhooks", "Task", "P3", 3, "Webhook endpoints for external integrations, retry logic, signature verification."),
        ("Add customer order notes", "Task", "P3", 2, "Allow customers to add notes during checkout, show in order details, admin can reply."),
        ("Create email notification system", "Task", "P2", 5, "Transactional emails with SendGrid, templates for order events, unsubscribe handling."),
        ("Implement SMS notifications", "Task", "P3", 5, "Twilio integration for order status SMS, opt-in required, delivery confirmations."),
        ("Add order cancellation by customer", "Story", "P3", 5, "Allow cancellation within 1 hour, automatic refund, restock inventory, send confirmation."),
        ("Create returns and exchanges portal", "Story", "P2", 8, "RMA request form, return labels, exchange options, refund tracking, 30-day window."),
        ("Implement order modification", "Task", "P3", 5, "Allow address changes before shipping, quantity adjustments, payment method updates."),
        ("Add subscription/recurring orders", "Story", "P3", 13, "Subscribe & save, recurring billing, skip/pause options, subscription management page."),
        ("Create backorder handling", "Task", "P2", 5, "Allow backorders, expected restock dates, partial fulfillment, automated notifications."),
        ("Implement split payments", "Task", "P3", 5, "Pay with multiple cards, gift card + credit card, store credit application."),
        ("Add order priority flagging", "Task", "P3", 3, "Admin can flag high-priority orders, expedited processing queue, special handling."),
        ("Bug: Payment webhook duplicates", "Bug", "P1", 3, "Stripe webhooks processed twice causing duplicate orders. Add idempotency keys, deduplication."),
        ("Implement 3D Secure authentication", "Task", "P2", 5, "SCA compliance for EU, challenge flow, liability shift, fallback to non-3DS."),
        ("Add multi-currency support", "Story", "P2", 8, "Currency selection, live exchange rates, display in user currency, charge in base currency."),
        ("Create order timeline/activity log", "Task", "P3", 3, "Audit trail of order events, timestamps, user actions, system events, admin view."),
        ("Implement order analytics dashboard", "Story", "P3", 8, "Sales metrics, conversion funnel, payment method breakdown, charts with Chart.js."),
    ]))
    
    # Sprint 4: 25 issues - Admin Dashboard & Inventory (8 Done, 10 In Progress, 7 To Do)
    issues_by_sprint.append([
        # 8 Done
        *generate_issues_with_status(4, ["Done"], 8, [
            ("Design admin dashboard layout", "Task", "P2", 3, "Responsive dashboard with sidebar navigation, breadcrumbs, metrics cards, chart sections."),
            ("Create sales overview widget", "Story", "P2", 5, "Today/week/month/year sales, line charts, YoY comparison, export data."),
            ("Build top products widget", "Story", "P3", 3, "Best sellers by revenue/quantity, period selector, drill-down to product detail."),
            ("Implement recent orders table", "Task", "P2", 3, "Sortable table, status badges, quick actions, search/filter, pagination."),
            ("Add low stock alerts widget", "Story", "P2", 5, "Products below reorder point, criticality levels, reorder suggestions."),
            ("Create customer metrics widget", "Story", "P3", 3, "New customers, repeat rate, lifetime value, churn rate, growth charts."),
            ("Implement real-time notifications", "Task", "P2", 5, "Toast notifications for new orders, low stock, WebSocket connection, sound alerts."),
            ("Bug: Dashboard charts not rendering", "Bug", "P2", 2, "Charts fail to load on initial page load. Add loading state, error boundaries."),
        ]),
        # 10 In Progress
        *generate_issues_with_status(4, ["In Progress"], 10, [
            ("Build inventory management interface", "Story", "P2", 8, "Stock levels table, bulk edit, import/export, warehouse views, adjustment history."),
            ("Implement barcode scanning", "Story", "P2", 5, "Camera/scanner integration, lookup products, quick stock updates, mobile support."),
            ("Create purchase order system", "Story", "P2", 13, "PO creation, supplier management, receiving workflow, partial receives, cost tracking."),
            ("Add stock transfer between warehouses", "Task", "P2", 5, "Transfer requests, in-transit tracking, automatic inventory adjustments."),
            ("Implement stocktake/audit tool", "Task", "P3", 5, "Physical count entry, variance reports, adjustment approvals, scheduled audits."),
            ("Create supplier portal", "Story", "P3", 8, "Login for suppliers, view POs, update delivery status, invoice upload."),
            ("Add inventory forecasting", "Story", "P3", 8, "Predictive analytics, seasonal trends, reorder suggestions, safety stock calculations."),
            ("Implement batch/lot tracking", "Task", "P2", 5, "Lot numbers, expiry dates, FIFO/LIFO, recall management, traceability."),
            ("Create inventory reports", "Task", "P2", 5, "Stock valuation, turnover rate, aging report, dead stock identification, export options."),
            ("Add product bundling", "Story", "P3", 5, "Create bundles, bundle pricing, inventory allocation, unbundle support."),
        ]),
        # 7 To Do
        *generate_issues_with_status(4, ["To Do"], 7, [
            ("Implement multi-location inventory", "Story", "P2", 8, "Inventory per location, transfer management, location-based availability."),
            ("Add automated reordering", "Story", "P3", 8, "Auto-generate POs when stock < reorder point, supplier selection, approval workflow."),
            ("Create inventory valuation methods", "Task", "P3", 5, "FIFO, LIFO, Weighted Average costing, financial reports."),
            ("Implement consignment inventory", "Task", "P3", 5, "Track consigned stock, sales-based billing, return unsold items."),
            ("Add inventory reservations", "Task", "P2", 3, "Reserve stock for quotes, hold periods, auto-release expired reservations."),
            ("Create inventory import tool", "Task", "P2", 3, "CSV/Excel import with validation, bulk updates, error reports, rollback."),
            ("Add product kitting/assembly", "Task", "P3", 5, "Combine components into finished goods, track component inventory, assembly costs."),
        ]),
    ])
    
    # Sprint 5 & 6: Remaining 13 issues (Planning/Backlog)
    sprint_5_6 = [
        ("Create analytics dashboard framework", "Story", "P2", 8, "Dashboard builder, widget library, custom metrics, drag-and-drop layout."),
        ("Implement customer segmentation", "Story", "P2", 8, "RFM analysis, cohort analysis, segment builder, targeted campaigns."),
        ("Add A/B testing framework", "Story", "P2", 13, "Experiment setup, variant distribution, statistical analysis, winner selection."),
        ("Create abandoned cart analytics", "Task", "P3", 5, "Cart abandonment rate, recovery rate, revenue impact, trend analysis."),
        ("Implement product performance reports", "Story", "P3", 5, "Sales by product, margin analysis, inventory turns, lifecycle stage."),
        ("Add customer lifetime value calculation", "Task", "P3", 3, "CLV formula, cohort LTV, prediction models, segmentation by LTV."),
        ("Create marketing attribution", "Story", "P2", 8, "Multi-touch attribution, channel performance, ROI calculations, conversion paths."),
        ("Implement advanced search analytics", "Task", "P3", 3, "Search terms report, zero-result queries, search-to-purchase rate, trends."),
        ("Add performance monitoring", "Task", "P2", 5, "APM with New Relic/DataDog, slow query detection, error tracking, uptime monitoring."),
        ("Create data export API", "Task", "P3", 5, "REST API for data exports, authentication, rate limiting, bulk operations."),
        ("Implement caching strategy", "Task", "P2", 5, "Redis for sessions/cache, CDN for static assets, query result caching, cache invalidation."),
        ("Add database query optimization", "Task", "P2", 5, "Index analysis, slow query optimization, query rewriting, connection pooling."),
        ("Create deployment automation", "Task", "P2", 3, "Zero-downtime deployments, blue-green strategy, rollback automation, health checks."),
    ]
    
    # Split Sprint 5 & 6
    issues_by_sprint.append(generate_issues_from_tuples(5, sprint_5_6[:7], "Backlog"))
    issues_by_sprint.append(generate_issues_from_tuples(6, sprint_5_6[7:], "Backlog"))
    
    return issues_by_sprint

def generate_sprint_issues(sprint_num, count, status, issue_tuples):
    """Generate issues from tuples for a sprint"""
    return generate_issues_from_tuples(sprint_num, issue_tuples[:count], status)

def generate_issues_from_tuples(sprint_num, issue_tuples, status):
    """Convert issue tuples to issue dictionaries"""
    issues = []
    for title, itype, priority, points, desc in issue_tuples:
        issues.append({
            "title": title,
            "type": itype,
            "status": status,
            "priority": priority,
            "story_points": points,
            "estimated_hours": points * 2.5,  # Rough conversion
            "assign": True if status in ["Done", "In Progress"] else False,
            "description": expand_description(title, desc),
        })
    return issues

def generate_issues_with_status(sprint_num, statuses, count, issue_tuples):
    """Generate issues with different statuses"""
    issues = []
    for i, (title, itype, priority, points, desc) in enumerate(issue_tuples[:count]):
        status = statuses[i % len(statuses)]
        issues.append({
            "title": title,
            "type": itype,
            "status": status,
            "priority": priority,
            "story_points": points,
            "estimated_hours": points * 2.5,
            "assign": status in ["Done", "In Progress"],
            "description": expand_description(title, desc),
        })
    return issues

def expand_description(title, short_desc):
    """Expand short description into rich Markdown content"""
    return f"""## Overview
{short_desc}

## Acceptance Criteria
- Implementation meets requirements
- Code reviewed and approved
- Unit tests written and passing
- Integration tests passing
- Documentation updated
- No breaking changes

## Technical Notes
See implementation details in technical spec doc.

## Related Issues
None

## Testing Strategy
- Unit tests for core logic
- Integration tests for API endpoints
- Manual QA testing
- Performance testing if applicable
"""
