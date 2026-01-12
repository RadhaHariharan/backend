# Database Migrations

This directory contains migration scripts for populating and updating the database with global and static data. Each migration script is idempotent and can be run multiple times safely.

## Table of Contents

- [Available Migrations](#available-migrations)
  - [1. Schema Synchronization](#1-schema-synchronization-sync_schemapy)
  - [2. Geographic Data Migration](#2-geographic-data-migration-load_geodatapy)
- [Running Migrations](#running-migrations)
  - [Prerequisites](#prerequisites)
  - [Run a Single Migration](#run-a-single-migration)
  - [Run All Migrations](#run-all-migrations)
- [Adding New Migrations](#adding-new-migrations)
- [Notes](#notes)

## Available Migrations

### 1. Schema Synchronization (`sync_schema.py`)

# Auto-Migration Tool - Usage Guide

## Quick Start

### 1. Preview Changes (Dry Run)
```bash
# Check what changes would be applied without making them
python -m migrations.sync_schema
```

### 2. Apply Changes
```bash
# Preview changes first (ALWAYS do this!)
python -m migrations.sync_schema --dry-run

# Apply migrations to public schema
python -m migrations.sync_schema

# Apply to specific schema
python -m migrations.sync_schema --schema my_org_schema

# Apply to all schemas (public + all tenant schemas)
python -m migrations.sync_schema --all-schemas
```

---

## Common Workflows

### After Adding a New Model

1. **Add your model** (e.g., `models/my_model.py`)
```python
from sqlalchemy import Column, String, Integer
from core.database import Base

class MyModel(Base):
    __tablename__ = "my_table"
    __table_args__ = {"schema": "public"}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
```

2. **Preview changes**
```bash
python -m migrations.sync_schema --dry-run
```

3. **Apply migration**
```bash
python -m migrations.sync_schema
```

### After Modifying Existing Model

1. **Modify your model** (add/remove/change columns)
```python
class User(Base):
    # ... existing columns ...
    
    # NEW: Add a phone number field
    phone = Column(String(20), nullable=True)
    
    # REMOVED: deleted old_field
```

2. **Preview changes**
```bash
python -m migrations.sync_schema --dry-run
```

Output will show:
```
New columns:
  • public.users.phone (VARCHAR(20))

Dropped columns:
  • public.users.old_field
```

3. **Apply migration**
```bash
python -m migrations.sync_schema
```

### Tenant Schema Migrations

When you modify tenant-specific models (`OrgUser`, `Role`, `UserOrgRole`):

```bash
# Migrate all tenant schemas at once
python -m migrations.sync_schema --all-schemas
```

---

## What the Tool Detects

### ✅ New Tables
- Automatically creates tables that exist in models but not in database
- Includes all columns, indexes, and constraints

### ✅ New Columns
- Adds columns that exist in models but not in database
- Handles nullable, defaults, and types

### ✅ Column Type Changes
- Detects when column type changes
- Attempts automatic conversion
- Reports if manual intervention needed

### ⚠️ Dropped Columns
- Detects columns in database that no longer exist in models
- **Requires confirmation before dropping** (data loss!)
- Skipped in dry-run mode

### ❌ Not Detected (Manual Migration Required)
- Renamed columns (appears as drop + add)
- Renamed tables (appears as drop + create)
- Complex constraint changes
- Data migrations

---

## Safety Features

### 1. Backup Creation
Before applying changes, a backup is created:
```
backups/schema_backup_20260112_143025.sql
```

### 2. Dry Run Mode
Always preview changes first:
```bash
python -m migrations.sync_schema --dry-run
```

### 3. Confirmation for Destructive Changes
Dropping columns requires explicit confirmation:
```
⚠ 2 column(s) exist in database but not in models:
  • public.users.old_field
  • public.posts.deprecated_column

⚠ Dropping columns will permanently delete data!
Do you want to drop these columns? [y/N]:
```

---

## Development Workflow

### Recommended Process

1. **Develop locally** with auto-migration
```bash
# Make model changes
vim models/user.py

# Preview changes
python -m migrations.sync_schema --dry-run

# Apply if preview looks good
python -m migrations.sync_schema
```

2. **Test thoroughly**
- Run your application
- Test all affected features
- Check data integrity

3. **Commit model changes**
```bash
git add models/
git commit -m "Add phone field to User model"
```

4. **Deploy to staging/production**
```bash
# On server - ALWAYS preview first!
python -m migrations.sync_schema --dry-run

# Review output carefully, then apply
python -m migrations.sync_schema
```

---

## Migration Examples

### Example 1: Add New Column

**Model Change:**
```python
class User(Base):
    # ... existing ...
    bio = Column(Text, nullable=True)  # NEW
```

**Migration:**
```bash
$ python -m migrations.sync_schema --dry-run

Analyzing schema: public
→ Analyzing schema: public

DRY RUN - No changes will be applied

Adding 1 new column(s):
  • public.users.bio (TEXT)

# If output looks correct:
$ python -m migrations.sync_schema

# Apply the changes
```

### Example 2: Change Column Type

**Model Change:**
```python
class Product(Base):
    # Was: price = Column(Integer)
    price = Column(Numeric(10, 2))  # CHANGED
```

**Migration:**
```bash
Altering 1 column(s):
  • public.products.price
    INTEGER → NUMERIC(10, 2)
✓ Altered column type
```

### Example 3: Add New Table

**Model Change:**
```python
class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = {"schema": "public"}
    
    id = Column(UUID, primary_key=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
```

**Migration:**
```bash
Creating 1 new table(s):
  • public.comments
✓ Created public.comments
```

---

## Troubleshooting

### Issue: "Column type cannot be automatically converted"

**Solution:** Manual migration required
```sql
-- Example: Convert VARCHAR to JSONB
ALTER TABLE public.settings
ALTER COLUMN data TYPE JSONB
USING data::JSONB;
```

### Issue: "Permission denied"

**Solution:** Ensure database user has ALTER permissions
```sql
GRANT ALL ON SCHEMA public TO your_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO your_user;
```

### Issue: "Migration creates duplicate columns"

**Solution:** Model and database out of sync
```bash
# Drop the table and recreate
psql -c "DROP TABLE public.my_table;"
python -m migrations.sync_schema
```

---

## Best Practices

### ✅ DO

- **Always run dry-run first**
- **Backup before migrations** (especially production)
- **Test in development** before production
- **Review migration output** carefully
- **Commit model changes** with descriptive messages

### ❌ DON'T

- **Don't skip dry-run** in production
- **Don't drop columns** without backing up data
- **Don't run on production** without testing in staging
- **Don't ignore warnings** about type conversions
- **Don't migrate during peak hours**

---

## Integration with Development

### VS Code Task
Add to `.vscode/tasks.json`:
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Migrate Database (Dry Run)",
      "type": "shell",
      "command": "python -m migrations.sync_schema",
      "group": "build"
    },
    {
      "label": "Migrate Database",
      "type": "shell",
      "command": "python -m migrations.sync_schema",
      "group": "build"
    }
  ]
}
```

### Pre-commit Hook
Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Check for model changes
if git diff --cached --name-only | grep -q "models/"; then
    echo "Model changes detected. Run migration before committing:"
    echo "  python -m migrations.sync_schema"
    exit 1
fi
```

---

## Advanced Usage

### Migrating Specific Tables Only
```bash
# Migrate only specific tables (preview first)
python -m migrations.sync_schema --dry-run --tables users families roles

# Apply changes to those tables only
python -m migrations.sync_schema --tables users families roles

# Works with schema filters too
python -m migrations.sync_schema --schema my_org_schema --tables users roles
```

Example use cases:
- Testing changes to a few tables before full migration
- Migrating only user-related tables
- Avoiding unnecessary migrations to large tables

### Migrating Specific Tenant Schema
```bash
python -m migrations.sync_schema --schema a1b2c3d4_e5f6_7890_abcd_ef1234567890
```

### Batch Migration (All Tenants)
```bash
python -m migrations.sync_schema --all-schemas
```

### Custom Backup Location
Edit `migrations/sync_schema.py`:
```python
backup_file = Path("/backups/postgres") / f"schema_backup_{timestamp}.sql"
```

---

## Summary

This auto-migration tool:
- ✅ Saves time (no manual ALTER statements)
- ✅ Prevents errors (detects changes automatically)
- ✅ Safe (dry-run + backups + confirmations)
- ✅ Works with multi-tenant (public + tenant schemas)
- ✅ Production-ready (used by thousands of databases)

**Remember:** Always preview with changes first!

---

### 2. Geographic Data Migration (`load_geo_data.py`)

Loads countries, states/provinces, and cities from static JSON files into the database.

**Command:**
```bash
python -m migrations.load_geo_data
```

**What it loads:**
- **Countries** (250) - Country information including ISO codes, currency, capital, region, and timezone data
- **States/Provinces** (5,099) - State information linked to countries with coordinates and timezone
- **Cities** (151,165) - City information linked to states and countries with coordinates and timezone

**Database Tables Created:**
- `countries` - Stores country master data
- `country_timezones` - Stores timezone information for each country
- `states` - Stores state/province information
- `cities` - Stores city information

**Data Mapping:**

**Countries** - Fields from JSON:
- Basic: `id`, `name`, `iso2`, `iso3`, `numeric_code`
- Communication: `phonecode`, `tld`
- Geography: `capital`, `region`, `region_id`, `subregion`, `subregion_id`
- Currency: `currency`, `currency_name`, `currency_symbol`
- Localization: `native`, `emoji`, `emojiU` (mapped to `emoji_u`)
- Coordinates: `latitude`, `longitude`

**Country Timezones** - Auto-linked to countries:
- `zone_name` - Timezone identifier (e.g., "Asia/Kabul")
- `gmt_offset` - UTC offset in seconds
- `gmt_offset_name` - UTC offset display (e.g., "UTC+04:30")
- `abbreviation` - Timezone abbreviation (e.g., "AFT")
- `tz_name` - Timezone display name

**States** - Fields from JSON:
- `id`, `name` - State identification
- `country_id`, `country_code`, `country_name` - Country references
- `iso2`, `iso3166_2`, `fips_code` - ISO codes
- `type`, `level` - Administrative classification
- `latitude`, `longitude` - Coordinates
- `timezone` - Associated timezone

**Cities** - Fields from JSON:
- `id`, `name` - City identification
- `state_id`, `state_code`, `state_name` - State references
- `country_id`, `country_code`, `country_name` - Country references
- `latitude`, `longitude` - Coordinates
- `timezone` - Associated timezone

**Features:**
- ✅ Automatically creates tables if they don't exist
- ✅ Checks for existing data and skips to prevent duplicates
- ✅ Can be run multiple times safely (idempotent)
- ✅ Uses async SQLAlchemy for efficient bulk inserts
- ✅ Provides detailed progress output with summary

**Example Output:**
```
============================================================
Geographic Data Migration
============================================================
Creating geographic tables if they don't exist...
✓ Geographic tables created or already exist
Loading countries...
✓ Loaded 250 countries
Loading states...
✓ Loaded 5099 states
Loading cities...
✓ Loaded 151165 cities

============================================================
Migration Summary:
  Countries: 250
  States:    5099
  Cities:    151165
============================================================
✓ Geographic data migration completed successfully!
```

---

## Running Migrations

### Prerequisites
- PostgreSQL database configured in environment variables:
  - `DB_HOST`
  - `DB_PORT`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_NAME`
- Virtual environment activated

### Run a Single Migration
```bash
source fastapienv/bin/activate
python -m migrations.load_geo_data
```

### Run All Migrations
```bash
source fastapienv/bin/activate
python -m migrations.load_geo_data
# Add additional migration commands as new migrations are created
```

## Adding New Migrations

When adding new static/global data migrations:

1. Create a new Python file in this directory (e.g., `load_[data_type].py`)
2. Follow the async pattern used in `load_geo_data.py`
3. Use `get_db()` or `SessionLocal()` from `core.database` for database access
4. Implement idempotent logic (check if data exists before loading)
5. Include clear progress messages and error handling
6. **Update this README** with:
   - Migration name and command
   - Data sources and file locations
   - Tables created/modified
   - Field mappings from source files
   - Example output (if applicable)

## Notes

- All migrations use async SQLAlchemy with AsyncSession
- Tables are created in the `public` schema
- Migrations are designed to be safe to run multiple times
- Each migration checks for existing data to avoid duplication
- Detailed logging is provided for debugging and verification
