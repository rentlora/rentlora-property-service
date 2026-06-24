import os
from functools import lru_cache

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "property-service"
    app_version: str = "1.0.0"
    database_url: str = ""
    jwt_secret: str = ""
    uploads_dir: str = "./uploads"
    s3_bucket: str = ""
    cloudfront_domain: str = ""
    aws_default_region: str = "us-east-1"
    internal_api_url: str = "http://localhost:8003"  # default local fallback
    # SQS queue that ai-search-service consumes to (re)generate property embeddings.
    # Empty -> event-driven path is disabled and we fall back to the direct HTTP embedding call.
    property_sync_queue_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def fetch_aws_config():
    """Pull config from Secrets Manager + Parameter Store in dev/prod.

    Sensitive values (db password, jwt) come from Secrets Manager; non-sensitive
    values (db host/user/name, bucket, CDN, queue URL, internal API URL) come
    from Parameter Store, each with a fallback. Credentials are resolved via the
    pod's IRSA role — no static keys, no .env.
    """
    env = os.getenv("ENV", "local")
    if env not in ["dev", "prod"]:
        return {}

    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    ssm = boto3.client("ssm", region_name=region)
    secrets = boto3.client("secretsmanager", region_name=region)

    def _param(name, default):
        try:
            return ssm.get_parameter(Name=name)["Parameter"]["Value"]
        except Exception:
            return default

    db_pass = secrets.get_secret_value(SecretId=f"/rentlora/{env}/db-password")["SecretString"]
    jwt_sec = secrets.get_secret_value(SecretId=f"/rentlora/{env}/jwt-secret")["SecretString"]

    db_endpoint = ssm.get_parameter(Name=f"/rentlora/{env}/db-endpoint")["Parameter"]["Value"]
    db_user = _param(f"/rentlora/{env}/db-user", "postgres")
    db_name = _param(f"/rentlora/{env}/db-name", "rentlora")
    s3_bucket = ssm.get_parameter(Name=f"/rentlora/{env}/s3-image-bucket")["Parameter"]["Value"]

    int_alb = _param(f"/rentlora/{env}/internal-alb-dns", "")
    internal_api_url = f"http://{int_alb}" if int_alb else "http://ai-service:8003"

    database_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_endpoint}/{db_name}"

    return {
        "database_url": database_url,
        "jwt_secret": jwt_sec,
        "aws_default_region": region,
        "s3_bucket": s3_bucket,
        "cloudfront_domain": _param(f"/rentlora/{env}/cloudfront-domain", ""),
        "internal_api_url": internal_api_url,
        "property_sync_queue_url": _param(f"/rentlora/{env}/property-sync-queue-url", ""),
    }


@lru_cache
def get_settings() -> Settings:
    aws_values = fetch_aws_config()
    return Settings(**aws_values)

# ci: path-filter test (only property-service should build)
