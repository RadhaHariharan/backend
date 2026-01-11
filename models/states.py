from sqlalchemy import (
    Column,
    String,
    Integer,
    Index
)
from core.database import Base


class State(Base):
    __tablename__ = "states"
    __table_args__ = (
        Index("ix_states_name", "name"),
        Index("ix_states_country", "country_id"),
        {"schema": "public"},
    )

    # Primary Key (numeric ID from source dataset)
    id = Column(Integer, primary_key=True, index=True)

    # State / Province
    name = Column(String(150), nullable=False)

    # Country
    country_id = Column(Integer, nullable=False)
    country_code = Column(String(5), nullable=False)
    country_name = Column(String(150), nullable=False)

    # ISO & Codes
    iso2 = Column(String(10), nullable=True)
    iso3166_2 = Column(String(20), nullable=True)
    fips_code = Column(String(20), nullable=True)

    # Administrative info
    type = Column(String(50), nullable=True)     # state, province, territory
    level = Column(String(50), nullable=True)
    parent_id = Column(String(50), nullable=True)

    # Geo
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)

    # Timezone
    timezone = Column(String(100), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<State id={self.id} name={self.name} "
            f"country={self.country_code}>"
        )
