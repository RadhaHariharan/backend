"""
Database migration script for loading geographic data
Loads countries, states, and cities from static JSON files into the database

Run with: python -m migrations.load_geo_data
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import SessionLocal, engine, Base
from models.country import Country
from models.country_timezone import CountryTimezone
from models.states import State
from models.cities import City


# Get the backend directory path
BACKEND_DIR = Path(__file__).parent.parent
STATIC_DIR = BACKEND_DIR / "static"


async def create_tables():
    """Create only geographic data tables if they don't exist"""
    
    print("Creating geographic tables if they don't exist...")
    
    # Import inside function to avoid circular imports
    from sqlalchemy.schema import CreateTable
    
    async with engine.begin() as conn:
        # Create public schema if it doesn't exist
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        
        # Create tables using the metadata of each model
        for table in [Country.__table__, CountryTimezone.__table__, State.__table__, City.__table__]:
            try:
                await conn.execute(CreateTable(table, if_not_exists=True))
            except Exception:
                # Table might already exist, continue
                pass
        
        await conn.commit()
    
    print("✓ Geographic tables created or already exist")


async def load_countries(session: AsyncSession) -> int:
    """Load countries from JSON file"""
    
    countries_file = STATIC_DIR / "countries.json"
    
    if not countries_file.exists():
        print(f"✗ Countries file not found: {countries_file}")
        return 0
    
    # Check if countries already exist
    existing = await session.execute(select(Country).limit(1))
    if existing.scalars().first():
        print("✓ Countries already exist, skipping...")
        return 0
    
    print("Loading countries...")
    
    with open(countries_file, "r", encoding="utf-8") as f:
        countries_data = json.load(f)
    
    countries_to_add = []
    
    for country_data in countries_data:
        country = Country(
            id=country_data.get("id"),
            name=country_data.get("name"),
            iso2=country_data.get("iso2"),
            iso3=country_data.get("iso3"),
            numeric_code=country_data.get("numeric_code"),
            phonecode=country_data.get("phonecode"),
            tld=country_data.get("tld"),
            capital=country_data.get("capital"),
            region=country_data.get("region"),
            region_id=country_data.get("region_id"),
            subregion=country_data.get("subregion"),
            subregion_id=country_data.get("subregion_id"),
            nationality=country_data.get("nationality"),
            currency=country_data.get("currency"),
            currency_name=country_data.get("currency_name"),
            currency_symbol=country_data.get("currency_symbol"),
            native=country_data.get("native"),
            latitude=country_data.get("latitude"),
            longitude=country_data.get("longitude"),
            emoji=country_data.get("emoji"),
            emoji_u=country_data.get("emojiU", ""),
        )
        
        # Add timezones if they exist in the data
        timezones_data = country_data.get("timezones", [])
        for tz_data in timezones_data:
            timezone = CountryTimezone(
                country_id=country_data.get("id"),
                zone_name=tz_data.get("zoneName"),
                gmt_offset=tz_data.get("gmtOffset"),
                gmt_offset_name=tz_data.get("gmtOffsetName"),
                abbreviation=tz_data.get("abbreviation"),
                tz_name=tz_data.get("tzName"),
            )
            country.timezones.append(timezone)
        
        countries_to_add.append(country)
    
    session.add_all(countries_to_add)
    await session.commit()
    
    print(f"✓ Loaded {len(countries_to_add)} countries")
    return len(countries_to_add)


async def load_states(session: AsyncSession) -> int:
    """Load states from JSON file"""
    
    states_file = STATIC_DIR / "states.json"
    
    if not states_file.exists():
        print(f"✗ States file not found: {states_file}")
        return 0
    
    # Check if states already exist
    existing = await session.execute(select(State).limit(1))
    if existing.scalars().first():
        print("✓ States already exist, skipping...")
        return 0
    
    print("Loading states...")
    
    with open(states_file, "r", encoding="utf-8") as f:
        states_data = json.load(f)
    
    states_to_add = []
    
    for state_data in states_data:
        state = State(
            id=state_data.get("id"),
            name=state_data.get("name"),
            country_id=state_data.get("country_id"),
            country_code=state_data.get("country_code"),
            country_name=state_data.get("country_name"),
            iso2=state_data.get("iso2"),
            iso3166_2=state_data.get("iso3166_2"),
            fips_code=state_data.get("fips_code"),
            type=state_data.get("type"),
            level=state_data.get("level"),
            parent_id=state_data.get("parent_id"),
            latitude=state_data.get("latitude"),
            longitude=state_data.get("longitude"),
            timezone=state_data.get("timezone"),
        )
        states_to_add.append(state)
    
    session.add_all(states_to_add)
    await session.commit()
    
    print(f"✓ Loaded {len(states_to_add)} states")
    return len(states_to_add)


async def load_cities(session: AsyncSession) -> int:
    """Load cities from JSON file"""
    
    cities_file = STATIC_DIR / "cities.json"
    
    if not cities_file.exists():
        print(f"✗ Cities file not found: {cities_file}")
        return 0
    
    # Check if cities already exist
    existing = await session.execute(select(City).limit(1))
    if existing.scalars().first():
        print("✓ Cities already exist, skipping...")
        return 0
    
    print("Loading cities...")
    
    with open(cities_file, "r", encoding="utf-8") as f:
        cities_data = json.load(f)
    
    cities_to_add = []
    
    for city_data in cities_data:
        city = City(
            id=city_data.get("id"),
            name=city_data.get("name"),
            state_id=city_data.get("state_id"),
            state_code=city_data.get("state_code"),
            state_name=city_data.get("state_name"),
            country_id=city_data.get("country_id"),
            country_code=city_data.get("country_code"),
            country_name=city_data.get("country_name"),
            latitude=city_data.get("latitude"),
            longitude=city_data.get("longitude"),
            timezone=city_data.get("timezone"),
        )
        cities_to_add.append(city)
    
    session.add_all(cities_to_add)
    await session.commit()
    
    print(f"✓ Loaded {len(cities_to_add)} cities")
    return len(cities_to_add)


async def main():
    """Main migration function"""
    
    print("=" * 60)
    print("Geographic Data Migration")
    print("=" * 60)
    
    try:
        # Create tables first
        await create_tables()
        
        async with SessionLocal() as session:
            countries_count = await load_countries(session)
            states_count = await load_states(session)
            cities_count = await load_cities(session)
            
            print("\n" + "=" * 60)
            print("Migration Summary:")
            print(f"  Countries: {countries_count}")
            print(f"  States:    {states_count}")
            print(f"  Cities:    {cities_count}")
            print("=" * 60)
            
            if countries_count > 0 or states_count > 0 or cities_count > 0:
                print("✓ Geographic data migration completed successfully!")
            else:
                print("⚠ No new data was loaded (all tables already populated)")
                
    except Exception as e:
        print(f"\n✗ Migration failed with error:")
        print(f"  {type(e).__name__}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
