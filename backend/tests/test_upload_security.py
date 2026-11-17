from pathlib import Path
import struct
import zlib

import pytest

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.seller import Seller


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def make_png_bytes(width: int = 2, height: int = 2) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_rows = (b"\x00" + (b"\x22\x66\xdd" * width)) * height
    idat = zlib.compress(raw_rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def make_jpeg_bytes(width: int = 2, height: int = 2) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xdb" + struct.pack(">HB", 67, 0) + (b"\x08" * 64)
        + b"\xff\xc0" + struct.pack(">HBHHBBBB", 11, 8, height, width, 1, 1, 0x11, 0)
        + b"\xff\xda" + struct.pack(">HBBBBBB", 8, 1, 1, 0x00, 0, 63, 0)
        + b"\x5a\xa5"
        + b"\xff\xd9"
    )


def make_webp_bytes(width: int = 2, height: int = 2) -> bytes:
    bits = ((width - 1) & 0x3FFF) | (((height - 1) & 0x3FFF) << 14)
    vp8l_payload = b"\x2f" + struct.pack("<I", bits) + b"\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00"
    pad = b"\x00" if (len(vp8l_payload) % 2 == 1) else b""
    riff_size = 4 + 8 + len(vp8l_payload) + len(pad)
    return (
        b"RIFF"
        + struct.pack("<I", riff_size)
        + b"WEBP"
        + b"VP8L"
        + struct.pack("<I", len(vp8l_payload))
        + vp8l_payload
        + pad
    )


@pytest.fixture
def isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    upload_root = tmp_path / "isolated_uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_root))
    return upload_root


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request: pytest.FixtureRequest) -> str:
    return request.param


def _stored_files(upload_root: Path) -> list[Path]:
    products_dir = upload_root / "products"
    if not products_dir.exists():
        return []
    return list(products_dir.iterdir())


def test_1_anonymous_upload_returns_401(client, prefix, isolated_upload_dir):
    res = client.post(
        f"{prefix}/upload/image",
        files={"file": ("item.png", make_png_bytes(), "image/png")},
    )
    assert res.status_code == 401
    assert _stored_files(isolated_upload_dir) == []


def test_2_customer_and_non_catalog_roles_return_403(client, headers, prefix, isolated_upload_dir):
    for user_id in (2, 6, 7, 8):  # customer, staff, employee, super_admin
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": ("item.png", make_png_bytes(), "image/png")},
            headers=headers(user_id),
        )
        assert res.status_code == 403
    assert _stored_files(isolated_upload_dir) == []


def test_3_authorized_admin_upload_succeeds_for_raster_formats(
    client, admin_headers, prefix, isolated_upload_dir
):
    samples = [
        ("photo.png", make_png_bytes(), "image/png", ".png"),
        ("photo.jpeg", make_jpeg_bytes(), "image/jpeg", ".jpg"),
        ("photo.webp", make_webp_bytes(), "image/webp", ".webp"),
    ]
    for name, payload, mime, canonical_ext in samples:
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": (name, payload, mime)},
            headers=admin_headers,
        )
        assert res.status_code == 201
        body = res.json()
        assert body["success"] is True
        assert body["message"] == "Image uploaded successfully."
        data = body["data"]
        assert data["filename"].startswith("prod_")
        assert data["filename"].endswith(canonical_ext)
        assert name not in data["filename"]
        assert data["relative_url"] == f"/uploads/products/{data['filename']}"
        assert data["url"].endswith(data["relative_url"])
        saved_path = isolated_upload_dir / "products" / data["filename"]
        assert saved_path.is_file()
        assert saved_path.read_bytes() == payload


def test_4_seller_permission_and_product_ownership_policy(
    client, headers, prefix, isolated_upload_dir
):
    png = make_png_bytes()

    # Active seller 4 owns Store A (seller_id=1) and Product 1 -> allowed
    ok_own = client.post(
        f"{prefix}/upload/image?product_id=1&seller_id=1",
        files={"file": ("own.png", png, "image/png")},
        headers=headers(4),
    )
    assert ok_own.status_code == 201

    # Seller 4 cannot upload targeting Seller 2's product (Product 2) or seller_id=2
    denied_other_product = client.post(
        f"{prefix}/upload/image?product_id=2",
        files={"file": ("other.png", png, "image/png")},
        headers=headers(4),
    )
    assert denied_other_product.status_code == 403

    denied_other_seller = client.post(
        f"{prefix}/upload/image?seller_id=2",
        files={"file": ("other.png", png, "image/png")},
        headers=headers(4),
    )
    assert denied_other_seller.status_code == 403

    # Nonexistent product returns 404
    missing_product = client.post(
        f"{prefix}/upload/image?product_id=9999",
        files={"file": ("missing.png", png, "image/png")},
        headers=headers(4),
    )
    assert missing_product.status_code == 404

    # Suspended seller is denied (403)
    with SessionLocal() as db:
        db.get(Seller, 1).status = "Suspended"
        db.commit()
    suspended_res = client.post(
        f"{prefix}/upload/image",
        files={"file": ("suspended.png", png, "image/png")},
        headers=headers(4),
    )
    assert suspended_res.status_code == 403


def test_5_invalid_corrupt_truncated_and_decompression_bomb_rejected(
    client, admin_headers, prefix, isolated_upload_dir, monkeypatch
):
    valid_png = make_png_bytes()
    corrupt_crc_png = valid_png[:-6] + b"\xff\xff" + valid_png[-4:]
    truncated_png = valid_png[:-10]
    truncated_jpeg = make_jpeg_bytes()[:-2]  # missing EOI
    truncated_webp = make_webp_bytes()[:-4]

    # Bomb dimensions: 5000x5000 exceeds default 4096 max_dimension & 16MP ceiling
    oversized_ihdr = struct.pack(">IIBBBBB", 5000, 5000, 8, 2, 0, 0, 0)
    dimension_bomb_png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", oversized_ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + _png_chunk(b"IEND", b"")
    )

    # Zlib stream bomb: 1x1 header (expects 4 raw bytes) but IDAT expands to 100 KB
    zlib_bomb_png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"\x00" * 102400))
        + _png_chunk(b"IEND", b"")
    )

    invalid_cases = [
        ("empty.png", b"", "image/png"),
        ("corrupt.png", corrupt_crc_png, "image/png"),
        ("truncated.png", truncated_png, "image/png"),
        ("truncated.jpg", truncated_jpeg, "image/jpeg"),
        ("truncated.webp", truncated_webp, "image/webp"),
        ("dim_bomb.png", dimension_bomb_png, "image/png"),
        ("zlib_bomb.png", zlib_bomb_png, "image/png"),
    ]
    for name, payload, mime in invalid_cases:
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": (name, payload, mime)},
            headers=admin_headers,
        )
        assert res.status_code == 400, f"Expected 400 for {name}, got {res.status_code}"

    assert _stored_files(isolated_upload_dir) == []


def test_6_spoofed_extension_or_mime_type_rejected(
    client, admin_headers, prefix, isolated_upload_dir
):
    png_bytes = make_png_bytes()

    cases = [
        # Non-image executable/script disguised as JPEG
        ("shell.jpg", b"#!/bin/sh\necho pwned\n", "image/jpeg", 400),
        ("binary.png", b"\x7fELF\x02\x01\x01\x00fake-elf", "image/png", 400),
        # Valid PNG bytes disguised with .jpg + image/jpeg
        ("disguised.jpg", png_bytes, "image/jpeg", 400),
        # Extension .png mismatched with Content-Type image/jpeg
        ("mismatch.png", png_bytes, "image/jpeg", 400),
        # Disallowed executable extension with image MIME
        ("exploit.php", png_bytes, "image/png", 415),
        # Disallowed generic MIME with .png extension
        ("item.png", png_bytes, "application/octet-stream", 415),
        # Trailing script appended after PNG IEND
        ("polyglot.png", png_bytes + b"<script>alert(1)</script>", "image/png", 400),
    ]
    for name, payload, mime, expected_status in cases:
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": (name, payload, mime)},
            headers=admin_headers,
        )
        assert res.status_code == expected_status, (
            f"Case {name} ({mime}) expected {expected_status}, got {res.status_code}"
        )

    assert _stored_files(isolated_upload_dir) == []


def test_7_oversized_file_returns_413(
    client, admin_headers, prefix, isolated_upload_dir, monkeypatch
):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 512)
    oversized_payload = make_png_bytes(width=32, height=32) + (b"A" * 1024)
    res = client.post(
        f"{prefix}/upload/image",
        files={"file": ("huge.png", oversized_payload, "image/png")},
        headers=admin_headers,
    )
    assert res.status_code == 413
    assert _stored_files(isolated_upload_dir) == []


def test_8_svg_uploads_are_rejected(client, admin_headers, prefix, isolated_upload_dir):
    svg_payload = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
    )
    for name, mime in [
        ("vector.svg", "image/svg+xml"),
        ("vector.svg", "image/png"),
        ("spoofed.png", "image/svg+xml"),
        ("spoofed.png", "image/png"),
    ]:
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": (name, svg_payload, mime)},
            headers=admin_headers,
        )
        assert res.status_code == 415

    assert _stored_files(isolated_upload_dir) == []


def test_9_directory_traversal_filenames_cannot_escape_upload_dir(
    client, admin_headers, prefix, isolated_upload_dir
):
    png_bytes = make_png_bytes()

    traversal_names = [
        "../../escaped.png",
        "..\\..\\escaped_win.png",
        "%2e%2e/%2e%2e/escaped_encoded.png",
        "subdir/nested.png",
        "bad\x00name.png",
        "bad%00name.png",
        "..",
        "../..",
    ]
    for malicious_name in traversal_names:
        res = client.post(
            f"{prefix}/upload/image",
            files={"file": (malicious_name, png_bytes, "image/png")},
            headers=admin_headers,
        )
        assert res.status_code in (400, 415), (
            f"Expected 400/415 for {malicious_name!r}, got {res.status_code}"
        )

    assert _stored_files(isolated_upload_dir) == []
    assert not (isolated_upload_dir / "escaped.png").exists()
    assert not (isolated_upload_dir.parent / "escaped.png").exists()
    assert not (isolated_upload_dir / "escaped_win.png").exists()
    assert not (isolated_upload_dir.parent / "escaped_win.png").exists()


def test_10_failed_storage_cleans_up_partial_files_and_hides_paths(
    client, admin_headers, prefix, isolated_upload_dir, monkeypatch
):
    def fail_link(src, dst):
        raise OSError(f"Simulated disk failure at {dst}")

    monkeypatch.setattr("app.services.upload_service.os.link", fail_link)

    res = client.post(
        f"{prefix}/upload/image",
        files={"file": ("clean.png", make_png_bytes(), "image/png")},
        headers=admin_headers,
    )
    assert res.status_code == 500
    detail = res.json().get("detail", "")
    assert detail == "Failed to store uploaded image."
    assert str(isolated_upload_dir) not in detail
    assert "Simulated disk failure" not in detail
    assert _stored_files(isolated_upload_dir) == []
