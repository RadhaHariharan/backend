from sqlalchemy import (
    Column,
    String,
    Integer,
    Index
)
from sqlalchemy.orm import relationship
from core.database import Base


class Country(Base):
    __tablename__ = "countries"
    __table_args__ = (
        Index("ix_countries_iso2", "iso2"),
        Index("ix_countries_iso3", "iso3"),
        {"schema": "public"},
    )

    # Primary Key (numeric ID from dataset)
    id = Column(Integer, primary_key=True, index=True)

    # Basic
    name = Column(String(100), nullable=False)

    # ISO Codes
    iso2 = Column(String(2), nullable=False)
    iso3 = Column(String(3), nullable=False)
    numeric_code = Column(String(3), nullable=False)

    # Communication & Web
    phonecode = Column(String(10), nullable=False)
    tld = Column(String(10), nullable=False)

    # Geography & Administration
    capital = Column(String(100), nullable=True)
    region = Column(String(50), nullable=True)
    region_id = Column(Integer, nullable=True)
    subregion = Column(String(100), nullable=True)
    subregion_id = Column(Integer, nullable=True)
    nationality = Column(String(100), nullable=False)

    # Currency
    currency = Column(String(3), nullable=False)
    currency_name = Column(String(100), nullable=False)
    currency_symbol = Column(String(10), nullable=False)

    # Localization
    native = Column(String(200), nullable=True)

    # Coordinates
    latitude = Column(String(20), nullable=False)
    longitude = Column(String(20), nullable=False)

    # Flags
    emoji = Column(String(10), nullable=False)
    emoji_u = Column(String(20), nullable=False)

    # Relationships
    timezones = relationship(
        "CountryTimezone",
        back_populates="country",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Country id={self.id} iso2={self.iso2} name={self.name}>"
