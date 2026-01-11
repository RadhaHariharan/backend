from sqlalchemy import (
    Column,
    String,
    Integer,
    Index
)
from core.database import Base


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (
        Index("ix_cities_name", "name"),
        Index("ix_cities_state_country", "state_id", "country_id"),
        {"schema": "public"},
    )

    # Primary Key (numeric ID from source dataset)
    id = Column(Integer, primary_key=True, index=True)

    # City
    name = Column(String(150), nullable=False)

    # State
    state_id = Column(Integer, nullable=False)
    state_code = Column(String(10), nullable=False)
    state_name = Column(String(150), nullable=False)

    # Country
    country_id = Column(Integer, nullable=False)
    country_code = Column(String(5), nullable=False)
    country_name = Column(String(150), nullable=False)

    # Geo
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)

    # Timezone
    timezone = Column(String(100), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<City id={self.id} name={self.name} "
            f"state={self.state_code} country={self.country_code}>"
        )
