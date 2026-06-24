from datetime import date

from auth import get_current_user
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import Booking, Property, Review, User
from schemas import ReviewCreate
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/property/{property_id}")
async def property_reviews(property_id: int, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Review, User)
            .join(User, User.id == Review.reviewer_id)
            .where(Review.property_id == property_id)
            .order_by(desc(Review.created_at))
        )
    ).all()
    avg_rating = await db.scalar(select(func.coalesce(func.avg(Review.rating), 0)).where(Review.property_id == property_id))
    total_reviews = await db.scalar(select(func.count(Review.id)).where(Review.property_id == property_id))
    return {
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at,
                "reviewer_name": u.name,
                "reviewer_avatar": u.avatar_url,
            }
            for r, u in rows
        ],
        "avg_rating": round(float(avg_rating or 0), 2),
        "total_reviews": total_reviews or 0,
    }


async def autocomplete_past_bookings(db: AsyncSession):
    today = date.today()
    stmt = select(Booking).where(and_(Booking.status == "confirmed", Booking.check_out < today))
    past = (await db.execute(stmt)).scalars().all()
    if past:
        for b in past:
            b.status = "completed"
            db.add(b)
        await db.commit()


@router.post("")
async def create_review(payload: ReviewCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await autocomplete_past_bookings(db)
    booking = await db.scalar(select(Booking).where(Booking.id == payload.booking_id))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.guest_id != user["id"]:
        raise HTTPException(status_code=403, detail="Booking does not belong to current user")
    if booking.property_id != payload.property_id:
        raise HTTPException(status_code=400, detail="Booking property mismatch")
    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Review allowed only after completed stay")
    already = await db.scalar(select(Review).where(Review.booking_id == payload.booking_id))
    if already:
        raise HTTPException(status_code=409, detail="Review already exists for this booking")
    review = Review(**payload.model_dump(), reviewer_id=user["id"])
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@router.get("/my")
async def my_reviews(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        await db.execute(
            select(Review, Property.title, Property.city)
            .join(Property, Property.id == Review.property_id)
            .where(Review.reviewer_id == user["id"])
            .order_by(desc(Review.created_at))
        )
    ).all()
    return [
        {
            "id": r.id,
            "booking_id": r.booking_id,
            "property_id": r.property_id,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at,
            "property_title": title,
            "property_city": city,
        }
        for r, title, city in rows
    ]


@router.delete("/{review_id}")
async def delete_review(review_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    review = await db.scalar(select(Review).where(Review.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if user["role"] != "admin" and review.reviewer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    await db.delete(review)
    await db.commit()
    return {"message": "Review deleted"}
