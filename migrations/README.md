# Database Migrations

This directory contains migration scripts for populating and updating the database with global and static data. Each migration script is idempotent and can be run multiple times safely.

## Table of Contents

- [Available Migrations](#available-migrations)
  - [1. Geographic Data Migration](#1-geographic-data-migration-load_geodatapy)
- [Running Migrations](#running-migrations)
  - [Prerequisites](#prerequisites)
  - [Run a Single Migration](#run-a-single-migration)
  - [Run All Migrations](#run-all-migrations)
- [Adding New Migrations](#adding-new-migrations)
- [Notes](#notes)

## Available Migrations

### 1. Geographic Data Migration (`load_geo_data.py`)

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
