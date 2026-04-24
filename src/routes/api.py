from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from src.models.db import db

router = APIRouter()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PropertyCreateModel(BaseModel):
    landlord_id: str
    landlord_name: str          # denormalised for display
    title: str
    description: str
    location: str
    rent_amount: float
    amenities: List[str]
    images: List[str]

class PropertyUpdateModel(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    rent_amount: Optional[float] = None
    amenities: Optional[List[str]] = None
    images: Optional[List[str]] = None
    is_available: Optional[bool] = None

class PropertyOutModel(BaseModel):
    id: str
    landlord_id: str
    landlord_name: Optional[str] = None
    title: str
    description: str
    location: str
    rent_amount: float
    amenities: List[str]
    images: List[str]
    is_available: bool
    created_at: datetime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def serialize_property(prop: dict) -> dict:
    prop["id"] = str(prop.pop("_id"))
    return prop

async def validate_landlord_token(landlord_id: str, token: str):
    """Validate that the session token belongs to this landlord in the DB."""
    from src.models.db import db as _db
    if not ObjectId.is_valid(landlord_id):
        raise HTTPException(status_code=400, detail="Invalid landlord ID")
    user = await _db.db.users.find_one({"_id": ObjectId(landlord_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Landlord not found")
    if user.get("session_token") != token:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid session token")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PropertyOutModel)
async def add_property(
    property: PropertyCreateModel,
    x_session_token: str = Header(..., description="Session token of the landlord"),
):
    await validate_landlord_token(property.landlord_id, x_session_token)

    new_prop = property.model_dump()
    new_prop["is_available"] = True
    new_prop["created_at"] = datetime.utcnow()
    result = await db.db.properties.insert_one(new_prop)
    new_prop["_id"] = result.inserted_id
    return serialize_property(new_prop)

@router.get("/", response_model=List[PropertyOutModel])
async def list_properties(
    location: Optional[str] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
):
    query = {"is_available": True}
    if location:
        query["location"] = {"$regex": location, "$options": "i"}
    if max_price:
        query["rent_amount"] = {"$lte": max_price}
    if search:
        # Full-text search across title and location
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"location": {"$regex": search, "$options": "i"}},
        ]
    properties_cursor = db.db.properties.find(query)
    properties = await properties_cursor.to_list(length=100)
    return [serialize_property(p) for p in properties]

@router.get("/landlord/{landlord_id}", response_model=List[PropertyOutModel])
async def get_landlord_properties(landlord_id: str):
    properties_cursor = db.db.properties.find({"landlord_id": landlord_id})
    properties = await properties_cursor.to_list(length=100)
    return [serialize_property(p) for p in properties]

@router.get("/{property_id}", response_model=PropertyOutModel)
async def get_property(property_id: str):
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid Property ID")
    prop = await db.db.properties.find_one({"_id": ObjectId(property_id)})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return serialize_property(prop)

@router.put("/{property_id}", response_model=PropertyOutModel)
async def update_property(
    property_id: str,
    update_data: PropertyUpdateModel,
    x_session_token: str = Header(..., description="Session token of the landlord"),
    x_user_id: str = Header(..., description="Landlord's user ID"),
):
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid Property ID")

    # Verify token
    await validate_landlord_token(x_user_id, x_session_token)

    # Ensure this landlord owns the property
    prop = await db.db.properties.find_one({"_id": ObjectId(property_id)})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.get("landlord_id") != x_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: you do not own this property")

    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db.db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": update_fields}
    )
    updated_prop = await db.db.properties.find_one({"_id": ObjectId(property_id)})
    return serialize_property(updated_prop)

@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: str,
    x_session_token: str = Header(..., description="Session token of the landlord"),
    x_user_id: str = Header(..., description="Landlord's user ID"),
):
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid Property ID")

    await validate_landlord_token(x_user_id, x_session_token)

    prop = await db.db.properties.find_one({"_id": ObjectId(property_id)})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.get("landlord_id") != x_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: you do not own this property")

    await db.db.properties.delete_one({"_id": ObjectId(property_id)})
