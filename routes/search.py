import httpx
from auth import get_current_user
from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models import Property
from pydantic import BaseModel
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/cities")
async def cities(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(distinct(Property.city)).where(Property.is_available.is_(True)).order_by(Property.city))).all()
    return {"cities": [r[0] for r in rows if r[0]]}


@router.get("/suggestions")
async def suggestions(q: str = Query(min_length=2), db: AsyncSession = Depends(get_db)):
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="q must be at least 2 characters")
    term = f"%{q.strip()}%"
    city_rows = (await db.execute(select(distinct(Property.city)).where(Property.city.ilike(term)).limit(5))).all()
    property_rows = (await db.execute(select(Property.id, Property.title).where(Property.title.ilike(term)).limit(5))).all()
    items = [{"type": "city", "label": c[0], "id": None} for c in city_rows]
    items.extend([{"type": "property", "label": p.title, "id": p.id} for p in property_rows])
    return {"suggestions": items}


class RagSearchRequest(BaseModel):
    query: str


@router.post("/rag")
async def rag_search(
    payload: RagSearchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    settings = get_settings()
    token = user["token"]

    # 1. Embed the search query using ai-service
    url_embed = f"{settings.internal_api_url}/api/ai/embed"
    async with httpx.AsyncClient() as client:
        resp_embed = await client.post(
            url_embed,
            json={"text": query},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )
        if resp_embed.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to get query embedding from AI service")
        query_embedding = resp_embed.json().get("embedding")

    if not query_embedding:
        raise HTTPException(status_code=500, detail="Received empty embedding")

    # 2. Search Postgres using vector cosine distance (<->)
    # Get top 5 matches
    stmt = (
        select(Property)
        .where(Property.is_available.is_(True))
        .where(Property.embedding.is_not(None))
        .order_by(Property.embedding.cosine_distance(query_embedding))
        .limit(5)
    )
    results = (await db.scalars(stmt)).all()

    if not results:
        return {"summary": "I couldn't find any properties matching your request.", "properties": []}

    # Serialize properties for AI summary and response
    props_list = []
    for p in results:
        props_list.append({
            "id": p.id,
            "title": p.title,
            "city": p.city,
            "country": p.country,
            "price_per_night": float(p.price_per_night),
            "max_guests": p.max_guests,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "description": p.description,
            "images": p.images
        })

    # 3. Generate RAG summary using ai-service
    url_rag = f"{settings.internal_api_url}/api/ai/rag"
    async with httpx.AsyncClient() as client:
        resp_rag = await client.post(
            url_rag,
            json={"query": query, "properties": props_list},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0
        )
        if resp_rag.status_code == 200:
            summary = resp_rag.json().get("summary", "Here are your matches.")
        else:
            # Fallback if generation fails
            summary = "Here are the best matching properties we found."

    return {
        "summary": summary,
        "properties": props_list
    }

