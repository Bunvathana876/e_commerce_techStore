from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from urllib.parse import quote, urlparse

from fastapi import HTTPException, status
import httpx

from app.core.config import Settings, settings


@dataclass(frozen=True)
class StoredFileResult:
    filename: str
    object_key: str
    url: str | None
    relative_url: str | None
    storage_backend: str


def _sign_hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _aws_signature_v4_headers(
    *,
    method: str,
    url: str,
    region: str,
    access_key: str,
    secret_key: str,
    payload: bytes,
    content_type: str,
    now: datetime | None = None,
) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = quote(parsed.path or "/", safe="/-_.~")
    timestamp = now or datetime.now(timezone.utc)
    amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = timestamp.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload).hexdigest()

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    k_date = _sign_hmac(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    k_region = _sign_hmac(k_date, region)
    k_service = _sign_hmac(k_region, "s3")
    k_signing = _sign_hmac(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Content-Type": content_type,
        "Host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": authorization,
    }


class StorageService:
    """Durable media storage supporting local disk (dev/test), Supabase Storage, and S3/R2."""

    @staticmethod
    def resolve_backend(cfg: Settings | None = None) -> str:
        c = cfg or settings
        explicit = (c.UPLOAD_STORAGE_BACKEND or "auto").strip().lower()
        if explicit in {"local", "supabase", "s3"}:
            return explicit
        if (
            c.SUPABASE_URL
            and c.SUPABASE_URL.strip()
            and c.SUPABASE_SERVICE_ROLE_KEY
            and c.SUPABASE_SERVICE_ROLE_KEY.strip()
        ):
            return "supabase"
        if (
            c.S3_BUCKET
            and c.S3_BUCKET.strip()
            and c.S3_ACCESS_KEY_ID
            and c.S3_ACCESS_KEY_ID.strip()
            and c.S3_SECRET_ACCESS_KEY
            and c.S3_SECRET_ACCESS_KEY.strip()
        ):
            return "s3"
        return "local"

    @staticmethod
    def store_product_image(
        data: bytes,
        *,
        canonical_ext: str,
        content_type: str,
        cfg: Settings | None = None,
    ) -> StoredFileResult:
        c = cfg or settings
        backend = StorageService.resolve_backend(c)
        unique_filename = f"prod_{secrets.token_hex(12)}{canonical_ext}"
        object_key = f"products/{unique_filename}"

        if backend == "supabase":
            url = StorageService._store_supabase(
                data=data,
                object_key=object_key,
                content_type=content_type,
                cfg=c,
            )
            return StoredFileResult(
                filename=unique_filename,
                object_key=object_key,
                url=url,
                relative_url=url,
                storage_backend="supabase",
            )

        if backend == "s3":
            url = StorageService._store_s3(
                data=data,
                object_key=object_key,
                content_type=content_type,
                cfg=c,
            )
            return StoredFileResult(
                filename=unique_filename,
                object_key=object_key,
                url=url,
                relative_url=url,
                storage_backend="s3",
            )

        stored_name = StorageService._store_local(data=data, canonical_ext=canonical_ext, cfg=c)
        relative = f"/uploads/products/{stored_name}"
        return StoredFileResult(
            filename=stored_name,
            object_key=f"products/{stored_name}",
            url=None,
            relative_url=relative,
            storage_backend="local",
        )

    @staticmethod
    def _store_local(data: bytes, *, canonical_ext: str, cfg: Settings) -> str:
        base_dir = (Path(cfg.UPLOAD_DIR).resolve() / "products").resolve()
        temp_path: Path | None = None
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            temp_name = f".tmp_{secrets.token_hex(16)}"
            temp_path = (base_dir / temp_name).resolve()
            if temp_path.parent != base_dir:
                raise HTTPException(status_code=400, detail="Invalid storage path.")

            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                view = memoryview(data)
                written = 0
                while written < len(view):
                    written += os.write(fd, view[written:])
                os.fsync(fd)
            finally:
                os.close(fd)

            for _ in range(5):
                unique_filename = f"prod_{secrets.token_hex(12)}{canonical_ext}"
                destination_path = (base_dir / unique_filename).resolve()
                if destination_path.parent != base_dir:
                    raise HTTPException(status_code=400, detail="Invalid storage destination.")
                try:
                    os.link(temp_path, destination_path)
                    return unique_filename
                except FileExistsError:
                    continue

            raise OSError("Unable to allocate unique upload filename.")
        except HTTPException:
            raise
        except OSError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store uploaded image.",
            ) from None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _store_supabase(
        *,
        data: bytes,
        object_key: str,
        content_type: str,
        cfg: Settings,
    ) -> str:
        base_url = (cfg.SUPABASE_URL or "").strip().rstrip("/")
        service_key = (cfg.SUPABASE_SERVICE_ROLE_KEY or "").strip()
        bucket = (cfg.SUPABASE_STORAGE_BUCKET or "product-images").strip().strip("/")
        if not base_url or not service_key or not bucket:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase Storage is selected but credentials are incomplete.",
            )

        upload_url = f"{base_url}/storage/v1/object/{bucket}/{object_key}"
        try:
            response = httpx.post(
                upload_url,
                content=data,
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "apikey": service_key,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                timeout=20.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Supabase Storage.",
            ) from exc

        if response.status_code >= 300:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Supabase Storage rejected image upload.",
            )

        if cfg.SUPABASE_STORAGE_PUBLIC_BASE_URL and cfg.SUPABASE_STORAGE_PUBLIC_BASE_URL.strip():
            return f"{cfg.SUPABASE_STORAGE_PUBLIC_BASE_URL.strip().rstrip('/')}/{object_key}"
        return f"{base_url}/storage/v1/object/public/{bucket}/{object_key}"

    @staticmethod
    def _store_s3(
        *,
        data: bytes,
        object_key: str,
        content_type: str,
        cfg: Settings,
    ) -> str:
        bucket = (cfg.S3_BUCKET or "").strip()
        access_key = (cfg.S3_ACCESS_KEY_ID or "").strip()
        secret_key = (cfg.S3_SECRET_ACCESS_KEY or "").strip()
        region = (cfg.S3_REGION or "auto").strip() or "auto"
        endpoint = (cfg.S3_ENDPOINT_URL or "").strip().rstrip("/")
        if not bucket or not access_key or not secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="S3 object storage is selected but credentials are incomplete.",
            )

        if endpoint:
            target_url = f"{endpoint}/{bucket}/{object_key}"
            sign_region = region
        else:
            sign_region = "us-east-1" if region == "auto" else region
            target_url = f"https://{bucket}.s3.{sign_region}.amazonaws.com/{object_key}"

        headers = _aws_signature_v4_headers(
            method="PUT",
            url=target_url,
            region=sign_region,
            access_key=access_key,
            secret_key=secret_key,
            payload=data,
            content_type=content_type,
        )

        try:
            response = httpx.put(
                target_url,
                content=data,
                headers=headers,
                timeout=20.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach S3 object storage.",
            ) from exc

        if response.status_code >= 300:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="S3 object storage rejected image upload.",
            )

        if cfg.S3_PUBLIC_BASE_URL and cfg.S3_PUBLIC_BASE_URL.strip():
            return f"{cfg.S3_PUBLIC_BASE_URL.strip().rstrip('/')}/{object_key}"
        return target_url
