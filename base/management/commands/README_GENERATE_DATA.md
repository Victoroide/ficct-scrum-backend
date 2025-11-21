# Generate Comprehensive Test Data Command

## Purpose

Critical data recovery command that rebuilds the entire database with production-quality test data after data loss.

## Files Created

1. **generate_comprehensive_test_data.py** - Main management command (665 lines)
2. **generate_test_data_helpers.py** - Templates and data (210 lines)

## Quick Reference

```bash
# Full generation with all features
docker-compose exec web_wsgi python manage.py generate_comprehensive_test_data

# Quick test (3 projects, skip external services)
docker-compose exec web_wsgi python manage.py generate_comprehensive_test_data \
    --projects=3 --skip-pinecone --skip-s3 --skip-csv

# Production full recovery
docker-compose exec web_wsgi python manage.py generate_comprehensive_test_data \
    --projects=15 --issues-per-project=50
```

## What Gets Created

### Core Data
- 6 user accounts (1 owner + 5 team members)
- 1 organization with all users
- 1 workspace for projects
- 10-20 projects (customizable)
- Issue types (6 per project)
- Workflow statuses (4 per project)
- Workflow transitions
- Project configurations
- Boards with columns

### Project Data
- Sprints (3-8 per Scrum project)
- Issues (500-1000 total, distributed)
- Comments (60% of issues get 1-5 comments)
- Issue links (10% of issues linked)

### Export Data
- 9 CSV files with all data
- S3 upload to datasets/generation_{timestamp}/
- Pinecone vector sync for all entities

## Generated Users

**Owner**: owner@ficct.com (Pass123)

**Team Members** (all Pass123):
- cvictorhugo39@gmail.com (Victor Cuellar)
- sebamendex11@gmail.com (Sebastian Mendez)
- l0nkdev04@gmail.com (Lonk Dev)
- jezabeltamara@gmail.com (Jezabel Tamara)
- rojas.wilder@ficct.uagrm.edu.bo (Wilder Rojas)

## Command Architecture

### 10 Execution Phases

1. **User Creation** - Creates accounts
2. **Organization Setup** - Creates org & workspace
3. **Project Generation** - Full project setup
4. **Sprint Generation** - Timeline-aware sprints
5. **Issue Generation** - Realistic issues with distribution
6. **Relationships** - Comments and links
7. **CSV Export** - Extract all data
8. **S3 Upload** - Preserve in cloud
9. **Pinecone Sync** - Vector embeddings
10. **Summary** - Report results

### Transaction Safety

All database operations run in a single atomic transaction:
- Complete success = all data committed
- Any failure = nothing committed (rollback)
- Safe to retry after fixing errors

## CSV Export Structure

### Files Generated

1. **organizations.csv** - Organization details
2. **workspaces.csv** - Workspace details
3. **users.csv** - User accounts (no passwords)
4. **projects.csv** - All projects
5. **sprints.csv** - Sprint records
6. **issues.csv** - All issues with details
7. **comments.csv** - Issue comments
8. **issue_links.csv** - Issue relationships
9. **metadata.csv** - Generation statistics

### S3 Upload Path

```
s3://ficct-scrum-bucket/
  datasets/
    generation_20251120_221530/
      ├── organizations.csv
      ├── workspaces.csv
      ├── users.csv
      ├── projects.csv
      ├── sprints.csv
      ├── issues.csv
      ├── comments.csv
      ├── issue_links.csv
      └── metadata.csv
```

## Data Quality Features

### Realism
- Issue titles relevant to project domain
- Comments make sense in context
- Dates follow logical progression
- Relationships properly formed

### Variety
- Different issue types (50% stories, 25% tasks, 15% bugs, 10% other)
- Various workflow statuses
- Mixed project methodologies (Scrum/Kanban)
- Diverse domains (healthcare, finance, e-commerce, etc.)

### Temporal Logic
- Created dates before updated dates
- Sprint dates don't overlap illogically
- Issue progression chronologically sound
- Activity concentrated in recent weeks
- Past data goes back 3-6 months

### Data Integrity
- Proper foreign key relationships
- No orphaned records
- Valid references between entities
- Logical parent-child structures

## Issue Distribution Examples

### E-Commerce Project (Active)
- 60 issues total
- 30 stories (user features)
- 15 tasks (technical work)
- 9 bugs (fixes)
- 6 epics/improvements
- Status distribution: 20% to-do, 40% in-progress, 30% in-review, 10% done

### Healthcare Project (Completed)
- 90 issues total
- All in "Done" status
- Full comments on most issues
- Complete sprint assignment
- Resolved dates set

## Customization

### Modify Project Templates

Edit `generate_test_data_helpers.py`:

```python
PROJECT_TEMPLATES.append({
    'name': 'Your Project',
    'key': 'PROJ',
    'description': 'Description',
    'methodology': 'scrum',  # or 'kanban'
    'status': 'active',      # planning, active, completed
    'priority': 'high',      # low, medium, high, critical
})
```

### Modify Issue Templates

Add to word banks in `generate_test_data_helpers.py`:

```python
ACTIONS.append('new_action')
FEATURES.append('new_feature')
COMPONENTS.append('new_component')
```

### Adjust Distribution

Modify percentages in `create_issues()` method:

```python
if type_choice < 0.60:  # Change from 0.50 to 0.60 for 60% stories
    issue_type = 'story'
```

## Performance

### Execution Time

| Scale | Projects | Issues | Time |
|-------|----------|--------|------|
| Small | 3 | ~100 | 10-30s |
| Medium | 10 | ~500 | 1-2min |
| Large | 20 | ~1000 | 3-5min |

**Additional time for:**
- CSV export: +10-20s
- S3 upload: +5-10s
- Pinecone sync: +30-60s

### Resource Usage

- Memory: ~200-500 MB
- CPU: Moderate (mostly database writes)
- Database: Grows by ~50-100 MB for full dataset
- Network: S3 upload ~1-5 MB, Pinecone depends on volume

## Troubleshooting

### "No module named 'generate_test_data_helpers'"

**Cause**: Helper file not found  
**Fix**: Ensure both files in `base/management/commands/`

### "Transaction aborted" or "IntegrityError"

**Cause**: Database constraint violation  
**Fix**: Clear database first or ensure all required fields provided

Common causes:
- Duplicate project keys
- Missing required foreign keys (created_by, assigned_to, etc.)
- Constraint violations on unique fields

### "S3 upload failed"

**Cause**: AWS credentials or permissions  
**Fix**:
1. Check .env has AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
2. Verify S3 bucket exists
3. Test with: `python manage.py test_s3`

### "Pinecone sync failed"

**Cause**: Pinecone not configured or sync command missing  
**Fix**:
1. Use `--skip-pinecone` flag
2. Configure Pinecone if needed
3. Ensure sync command exists

### Docker not running

**Cause**: Docker containers not started  
**Fix**:
```bash
docker-compose up -d
docker-compose ps  # Verify running
```

## Verification Checklist

After running command:

- [ ] Check user count: `SELECT COUNT(*) FROM auth_users;`
- [ ] Login with owner@ficct.com / Pass123
- [ ] Browse projects in UI
- [ ] View issues in at least one project
- [ ] Check sprints exist for Scrum projects
- [ ] Verify comments appear on issues
- [ ] Test API endpoints
- [ ] Check S3 for CSV files (if uploaded)
- [ ] Query Pinecone for vectors (if synced)
- [ ] Review command output for errors

## Maintenance

### Regular Updates

Update templates quarterly or when:
- New project types needed
- Issue categories change
- Workflow changes
- Team structure evolves

### Data Cleanup

Before re-running:
```bash
# Option 1: Drop and recreate database
docker-compose exec db psql -U postgres -c "DROP DATABASE ficct_scrum;"
docker-compose exec db psql -U postgres -c "CREATE DATABASE ficct_scrum;"
docker-compose exec web_wsgi python manage.py migrate

# Option 2: Delete all data (keeps schema)
docker-compose exec web_wsgi python manage.py flush --no-input
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Generate test data
  run: |
    docker-compose up -d
    docker-compose exec -T web_wsgi python manage.py generate_comprehensive_test_data \
      --projects=5 \
      --skip-s3 \
      --skip-pinecone
```

### Pre-commit Hook Example

```bash
#!/bin/bash
# Ensure test data is fresh before commits
docker-compose exec web_wsgi python manage.py generate_comprehensive_test_data \
    --projects=3 \
    --skip-s3 \
    --skip-pinecone \
    --skip-csv
```

## Security Considerations

1. **Passwords**: All users have same password (Pass123) - only for development
2. **CSV Export**: User passwords NOT included in CSV
3. **S3 Upload**: Files set to private ACL
4. **API Keys**: Not included in generated data
5. **Production**: Do NOT run this command in production

## Future Enhancements

Potential additions:
- [ ] Attachments (with mock files)
- [ ] Notifications (historical)
- [ ] Activity logs (detailed)
- [ ] Watchers on issues
- [ ] Labels and tags
- [ ] Custom fields
- [ ] Time tracking entries
- [ ] Webhooks/integrations

## Contributing

To add new templates or modify behavior:

1. Edit `generate_test_data_helpers.py` for data templates
2. Edit `generate_comprehensive_test_data.py` for logic
3. Test with small dataset first
4. Update this documentation
5. Submit PR with examples

## License

Part of FICCT-Scrum project. See main project LICENSE.

## Contact

For questions or issues with this command:
- Check main docs: `docs/DATA_GENERATION_GUIDE.md`
- Review code comments in command files
- Check Docker logs: `docker-compose logs web_wsgi`
- Test incrementally with skip flags
