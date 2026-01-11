from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship
from core.database import Base


class CountryTimezone(Base):
    __tablename__ = "country_timezones"
    __table_args__ = (
        Index("ix_country_timezones_country", "country_id"),
        Index("ix_country_timezones_zone", "zone_name"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    country_id = Column(
        Integer,
        ForeignKey("public.countries.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Timezone details
    zone_name = Column(String(100), nullable=False)       # Asia/Kolkata
    gmt_offset = Column(Integer, nullable=False)          # 19800
    gmt_offset_name = Column(String(10), nullable=False)  # UTC+05:30
    abbreviation = Column(String(10), nullable=False)     # IST
    tz_name = Column(String(100), nullable=False)         # India Standard Time

    # Relationships
    country = relationship(
        "Country",
        back_populates="timezones",
    )

    def __repr__(self) -> str:
        return (
            f"<CountryTimezone country_id={self.country_id} "
            f"zone={self.zone_name}>"
        )
