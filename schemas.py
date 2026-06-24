from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PropertyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    city: str
    country: str = "India"
    price_per_night: Decimal
    max_guests: int
    bedrooms: int = 1
    bathrooms: int = 1
    property_type: str
    amenities: list[str] = []
    images: list[str] = []


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    price_per_night: Optional[Decimal] = None
    max_guests: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_type: Optional[str] = None
    amenities: Optional[list[str]] = None
    images: Optional[list[str]] = None
    is_available: Optional[bool] = None

class ReviewCreate(BaseModel):
    property_id: int
    booking_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class AvailabilityQuery(BaseModel):
    check_in: date
    check_out: date
