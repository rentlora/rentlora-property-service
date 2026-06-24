import asyncio
import os
import sys

import httpx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

# We need an admin token to call ai-service if auth is enabled
# For this script, we'll assume it's running internally or we can use a service token.
# To make it simple, let's create a generic token or assume ai-service handles the raw request internally.
# Wait, auth expects a token. We can generate an admin token using auth.py for the script.
import jwt
from config import get_settings
from database import async_session_maker
from models import Property
from sqlalchemy import select


def generate_admin_token(secret: str):
    payload = {
        "sub": "0",  # System ID
        "email": "system@rentlora.local",
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def main():
    settings = get_settings()
    token = generate_admin_token(settings.jwt_secret)
    url = f"{settings.internal_api_url}/api/ai/embed"

    print("Starting embeddings backfill...")

    async with async_session_maker() as db:
        # Get properties without an embedding
        result = await db.scalars(select(Property).where(Property.embedding.is_(None)))
        properties = result.all()

        if not properties:
            print("No properties need backfilling.")
            return

        print(f"Found {len(properties)} properties to backfill.")

        async with httpx.AsyncClient() as client:
            for prop in properties:
                amenities_str = ", ".join(prop.amenities) if prop.amenities else "No special amenities"
                text_to_embed = f"Title: {prop.title}\n" \
                                f"Property Type: {prop.property_type}\n" \
                                f"Location: {prop.city}, {prop.country} ({prop.location or ''})\n" \
                                f"Price: ${prop.price_per_night} per night\n" \
                                f"Capacity: Up to {prop.max_guests} guests, {prop.bedrooms} bedrooms, {prop.bathrooms} bathrooms.\n" \
                                f"Amenities: {amenities_str}\n" \
                                f"Description: {prop.description or ''}"

                print(f"Processing Property ID {prop.id} ({prop.title})...")

                try:
                    resp = await client.post(
                        url,
                        json={"text": text_to_embed},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15.0
                    )

                    if resp.status_code == 200:
                        embedding = resp.json().get("embedding")
                        if embedding:
                            prop.embedding = embedding
                            db.add(prop)
                            await db.commit()
                            print(f"✅ Saved embedding for Property ID {prop.id}")
                        else:
                            print(f"❌ Empty embedding returned for Property ID {prop.id}")
                    else:
                        print(f"❌ AI Service returned {resp.status_code}: {resp.text}")
                except Exception as e:
                    print(f"❌ Error processing Property ID {prop.id}: {e}")

    print("Backfill complete.")


if __name__ == "__main__":
    asyncio.run(main())
