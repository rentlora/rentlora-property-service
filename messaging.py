"""SQS messaging for property-service.

Publishes property-change events to the `property-sync` queue, which
ai-search-service consumes to (re)generate vector embeddings. All AWS calls
rely on the pod's IRSA ServiceAccount identity — there are no static
credentials anywhere in this module.
"""
import json
import logging
from functools import lru_cache

import boto3
from config import get_settings

logger = logging.getLogger("property-service.messaging")
settings = get_settings()


@lru_cache
def _sqs_client():
    return boto3.client("sqs", region_name=settings.aws_default_region)


def publish_property_sync(property_id: int, operation: str = "upsert") -> bool:
    """Publish a property-change event to the property-sync SQS queue.

    Returns True if the message was sent, False if the queue is not configured
    (local/dev fallback) or the send failed.
    """
    queue_url = settings.property_sync_queue_url
    if not queue_url:
        return False
    try:
        _sqs_client().send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"property_id": property_id, "operation": operation}),
        )
        logger.info(f"Published property-sync event for property {property_id} ({operation})")
        return True
    except Exception as e:
        logger.error(f"Failed to publish property-sync event for {property_id}: {e}")
        return False


def sqs_health_check() -> dict:
    """IRSA verification helper.

    Performs a read-only GetQueueAttributes call. Success proves the pod can
    authenticate to SQS via its ServiceAccount IAM role without any static keys.
    """
    queue_url = settings.property_sync_queue_url
    if not queue_url:
        return {"irsa": "unconfigured", "detail": "property_sync_queue_url is not set"}
    try:
        attrs = _sqs_client().get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        return {
            "irsa": "ok",
            "sqs": "reachable",
            "queue_url": queue_url,
            "approx_messages": attrs.get("Attributes", {}).get("ApproximateNumberOfMessages"),
        }
    except Exception as e:
        logger.error(f"SQS IRSA health check failed: {e}")
        return {"irsa": "failed", "error": str(e)}
