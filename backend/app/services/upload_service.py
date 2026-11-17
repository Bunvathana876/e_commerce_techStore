import os
from pathlib import Path
import secrets
import struct
from typing import BinaryIO
from urllib.parse import unquote
import zlib

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product import Product
from app.models.user import User
from app.services.authorization_service import AuthorizationService

READ_CHUNK_SIZE = 64 * 1024

EXT_TO_FORMAT: dict[str, str] = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
}

MIME_TO_FORMAT: dict[str, str] = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}

FORMAT_TO_CANONICAL_EXT: dict[str, str] = {
    "jpeg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_ALLOWED_DEPTHS: dict[int, set[int]] = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}
PNG_CHANNELS: dict[int, int] = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3,
    0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB,
    0xCD, 0xCE, 0xCF,
}
JPEG_STANDALONE_MARKERS = {0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7}


class UploadService:
    @staticmethod
    def authorize_upload(
        db: Session,
        current_user: User,
        product_id: int | None = None,
        seller_id: int | None = None,
    ) -> None:
        if current_user.role == "seller" and not AuthorizationService.seller_ids(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An active seller account is required.",
            )

        if seller_id is not None:
            AuthorizationService.require_seller(db, current_user, seller_id)

        if product_id is not None:
            product = db.get(Product, product_id)
            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found.",
                )
            if not AuthorizationService.is_admin(current_user):
                if product.seller_id not in AuthorizationService.seller_ids(db, current_user):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Permission denied for this product.",
                    )

    @staticmethod
    def validate_and_store_product_image(file: UploadFile) -> str:
        declared_format = UploadService._validate_upload_metadata(
            filename=file.filename,
            content_type=file.content_type,
        )
        raw_bytes = UploadService._read_bounded_bytes(
            stream=file.file,
            max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        )
        detected_format = UploadService._sniff_and_verify_image(
            data=raw_bytes,
            expected_format=declared_format,
            max_dimension=settings.MAX_IMAGE_DIMENSION,
            max_pixels=settings.MAX_IMAGE_PIXELS,
        )
        return UploadService._atomic_store_bytes(
            data=raw_bytes,
            canonical_ext=FORMAT_TO_CANONICAL_EXT[detected_format],
        )

    @staticmethod
    def _validate_upload_metadata(filename: str | None, content_type: str | None) -> str:
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid image filename is required.",
            )

        decoded_name = unquote(filename)
        for candidate in (filename, decoded_name):
            if "\x00" in candidate or any(ord(ch) < 32 for ch in candidate):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid characters in upload filename.",
                )
            normalized_parts = candidate.replace("\\", "/").split("/")
            if ".." in normalized_parts or len(normalized_parts) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Directory paths are not permitted in upload filenames.",
                )

        leaf_name = Path(decoded_name).name.strip()
        if not leaf_name or leaf_name in {".", ".."} or ".." in leaf_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid image filename is required.",
            )

        ext = Path(leaf_name).suffix.lower()
        if ext not in EXT_TO_FORMAT:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported image format. Allowed formats: JPEG, PNG, WebP.",
            )

        normalized_mime = (content_type or "").split(";", 1)[0].strip().lower()
        if normalized_mime not in MIME_TO_FORMAT:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported media type. Allowed types: image/jpeg, image/png, image/webp.",
            )

        ext_format = EXT_TO_FORMAT[ext]
        mime_format = MIME_TO_FORMAT[normalized_mime]
        if ext_format != mime_format:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension does not match declared Content-Type.",
            )

        return ext_format

    @staticmethod
    def _read_bounded_bytes(stream: BinaryIO, max_bytes: int) -> bytes:
        buffer = bytearray()
        while True:
            chunk = stream.read(READ_CHUNK_SIZE)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Image exceeds maximum allowed size of {max_bytes} bytes.",
                )

        if not buffer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty.",
            )
        return bytes(buffer)

    @staticmethod
    def _sniff_format(data: bytes) -> str | None:
        if data.startswith(PNG_SIGNATURE):
            return "png"
        if len(data) >= 4 and data[:2] == b"\xff\xd8" and data[2:3] == b"\xff":
            return "jpeg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        return None

    @staticmethod
    def _looks_like_text_or_svg(data: bytes) -> bool:
        head = data[:512].lstrip().lower()
        return head.startswith((b"<svg", b"<?xml", b"<!doctype", b"<html", b"<script"))

    @staticmethod
    def _check_dimensions(
        width: int,
        height: int,
        max_dimension: int,
        max_pixels: int,
    ) -> None:
        if width <= 0 or height <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image dimensions.",
            )
        if width > max_dimension or height > max_dimension or (width * height) > max_pixels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image dimensions exceed safe limits.",
            )

    @staticmethod
    def _sniff_and_verify_image(
        data: bytes,
        expected_format: str,
        max_dimension: int,
        max_pixels: int,
    ) -> str:
        if UploadService._looks_like_text_or_svg(data):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="SVG and markup uploads are not permitted.",
            )

        actual_format = UploadService._sniff_format(data)
        if actual_format is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is not a valid supported raster image.",
            )

        if actual_format != expected_format:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image content does not match declared file format.",
            )

        if actual_format == "png":
            UploadService._verify_png(data, max_dimension, max_pixels)
        elif actual_format == "jpeg":
            UploadService._verify_jpeg(data, max_dimension, max_pixels)
        elif actual_format == "webp":
            UploadService._verify_webp(data, max_dimension, max_pixels)

        return actual_format

    @staticmethod
    def _verify_png(data: bytes, max_dimension: int, max_pixels: int) -> None:
        if len(data) < 33 or not data.startswith(PNG_SIGNATURE):
            raise HTTPException(status_code=400, detail="Corrupt or truncated PNG image.")

        pos = 8
        seen_ihdr = False
        seen_plte = False
        seen_idat = False
        seen_iend = False
        width = height = bit_depth = color_type = interlace = 0
        expected_raw = 0
        max_raw_cap = 0
        decompressor = zlib.decompressobj()
        decompressed_len = 0
        first_filter_check_buf = bytearray()
        row_stride = 0

        while pos < len(data):
            if seen_iend or pos + 12 > len(data):
                raise HTTPException(status_code=400, detail="Corrupt or truncated PNG image.")

            length = struct.unpack(">I", data[pos:pos + 4])[0]
            chunk_type = data[pos + 4:pos + 8]
            chunk_end = pos + 8 + length
            if chunk_end + 4 > len(data):
                raise HTTPException(status_code=400, detail="Truncated PNG chunk.")

            chunk_data = data[pos + 8:chunk_end]
            expected_crc = struct.unpack(">I", data[chunk_end:chunk_end + 4])[0]
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                raise HTTPException(status_code=400, detail="Corrupt PNG checksum.")

            pos = chunk_end + 4

            if not seen_ihdr:
                if chunk_type != b"IHDR" or length != 13:
                    raise HTTPException(status_code=400, detail="Invalid PNG header.")
                (
                    width,
                    height,
                    bit_depth,
                    color_type,
                    compression,
                    filter_method,
                    interlace,
                ) = struct.unpack(">IIBBBBB", chunk_data)
                UploadService._check_dimensions(width, height, max_dimension, max_pixels)

                if (
                    color_type not in PNG_ALLOWED_DEPTHS
                    or bit_depth not in PNG_ALLOWED_DEPTHS[color_type]
                    or compression != 0
                    or filter_method != 0
                    or interlace not in (0, 1)
                ):
                    raise HTTPException(status_code=400, detail="Unsupported or invalid PNG header parameters.")

                bits_per_pixel = bit_depth * PNG_CHANNELS[color_type]
                row_bytes = (width * bits_per_pixel + 7) // 8
                row_stride = 1 + row_bytes
                expected_raw = height * row_stride
                # Adam7 interlacing adds at most 7 sub-pass filter columns.
                max_raw_cap = expected_raw + (height * 7 if interlace == 1 else 0)
                seen_ihdr = True
            elif chunk_type == b"IHDR":
                raise HTTPException(status_code=400, detail="Duplicate PNG header.")
            elif chunk_type == b"PLTE":
                if length == 0 or length % 3 != 0 or length > 768:
                    raise HTTPException(status_code=400, detail="Invalid PNG palette.")
                seen_plte = True
            elif chunk_type == b"IDAT":
                if length > 0:
                    seen_idat = True
                    remaining = (max_raw_cap + 1) - decompressed_len
                    if remaining <= 0:
                        raise HTTPException(status_code=400, detail="PNG exceeds safe decompression limits.")
                    try:
                        out = decompressor.decompress(chunk_data, remaining)
                    except zlib.error:
                        raise HTTPException(status_code=400, detail="Corrupt PNG compressed data.") from None
                    decompressed_len += len(out)
                    if decompressor.unconsumed_tail or decompressed_len > max_raw_cap:
                        raise HTTPException(status_code=400, detail="PNG exceeds safe decompression limits.")
                    if interlace == 0 and row_stride > 0:
                        first_filter_check_buf.extend(out)
                        while len(first_filter_check_buf) >= row_stride:
                            if first_filter_check_buf[0] > 4:
                                raise HTTPException(status_code=400, detail="Invalid PNG scanline filter.")
                            del first_filter_check_buf[:row_stride]
            elif chunk_type == b"IEND":
                if length != 0:
                    raise HTTPException(status_code=400, detail="Invalid PNG trailer.")
                seen_iend = True

        if not (seen_ihdr and seen_idat and seen_iend) or pos != len(data):
            raise HTTPException(status_code=400, detail="Incomplete or corrupt PNG image.")
        if color_type == 3 and not seen_plte:
            raise HTTPException(status_code=400, detail="Missing PNG palette.")

        try:
            tail = decompressor.flush()
        except zlib.error:
            raise HTTPException(status_code=400, detail="Corrupt PNG stream trailer.") from None

        decompressed_len += len(tail)
        if not decompressor.eof or decompressed_len <= 0 or decompressed_len > max_raw_cap:
            raise HTTPException(status_code=400, detail="Truncated or invalid PNG image data.")
        if interlace == 0:
            if tail and row_stride > 0:
                first_filter_check_buf.extend(tail)
                while len(first_filter_check_buf) >= row_stride:
                    if first_filter_check_buf[0] > 4:
                        raise HTTPException(status_code=400, detail="Invalid PNG scanline filter.")
                    del first_filter_check_buf[:row_stride]
            if decompressed_len != expected_raw or len(first_filter_check_buf) != 0:
                raise HTTPException(status_code=400, detail="Corrupt PNG pixel data length.")

    @staticmethod
    def _verify_jpeg(data: bytes, max_dimension: int, max_pixels: int) -> None:
        if len(data) < 20 or data[:2] != b"\xff\xd8":
            raise HTTPException(status_code=400, detail="Corrupt or truncated JPEG image.")

        pos = 2
        seen_sof = False
        seen_sos = False
        seen_eoi = False
        n = len(data)

        while pos < n:
            if data[pos] != 0xFF:
                raise HTTPException(status_code=400, detail="Corrupt JPEG marker stream.")
            while pos < n and data[pos] == 0xFF:
                pos += 1
            if pos >= n:
                raise HTTPException(status_code=400, detail="Truncated JPEG marker.")

            marker = data[pos]
            pos += 1

            if marker == 0xD9:  # EOI
                seen_eoi = True
                break
            if marker == 0xD8 or marker == 0x00:
                raise HTTPException(status_code=400, detail="Unexpected JPEG marker.")
            if marker in JPEG_STANDALONE_MARKERS:
                continue

            if pos + 2 > n:
                raise HTTPException(status_code=400, detail="Truncated JPEG segment length.")
            seg_len = struct.unpack(">H", data[pos:pos + 2])[0]
            if seg_len < 2 or pos + seg_len > n:
                raise HTTPException(status_code=400, detail="Truncated JPEG segment.")
            payload = data[pos + 2:pos + seg_len]
            pos += seg_len

            if marker in JPEG_SOF_MARKERS:
                if len(payload) < 6:
                    raise HTTPException(status_code=400, detail="Corrupt JPEG frame header.")
                precision, height, width, components = struct.unpack(">BHHB", payload[:6])
                UploadService._check_dimensions(width, height, max_dimension, max_pixels)
                if (
                    precision not in (8, 12, 16)
                    or components not in (1, 3, 4)
                    or len(payload) != 6 + 3 * components
                ):
                    raise HTTPException(status_code=400, detail="Invalid JPEG frame parameters.")
                for idx in range(components):
                    sampling = payload[6 + idx * 3 + 1]
                    h_samp, v_samp = sampling >> 4, sampling & 0x0F
                    if not (1 <= h_samp <= 4 and 1 <= v_samp <= 4):
                        raise HTTPException(status_code=400, detail="Invalid JPEG sampling factors.")
                seen_sof = True
            elif marker == 0xDA:  # SOS
                if not seen_sof or len(payload) < 4:
                    raise HTTPException(status_code=400, detail="Invalid JPEG scan order.")
                scan_components = payload[0]
                if not (1 <= scan_components <= 4) or len(payload) != 1 + 2 * scan_components + 3:
                    raise HTTPException(status_code=400, detail="Corrupt JPEG scan header.")
                seen_sos = True

                # Scan entropy-coded bytes until the next unstuffed marker.
                entropy_bytes = 0
                while pos < n:
                    if data[pos] != 0xFF:
                        entropy_bytes += 1
                        pos += 1
                        continue
                    if pos + 1 >= n:
                        raise HTTPException(status_code=400, detail="Truncated JPEG scan data.")
                    nxt = data[pos + 1]
                    if nxt == 0x00:
                        entropy_bytes += 1
                        pos += 2
                        continue
                    if nxt == 0xFF:
                        pos += 1
                        continue
                    if 0xD0 <= nxt <= 0xD7:
                        pos += 2
                        continue
                    break

                if entropy_bytes == 0:
                    raise HTTPException(status_code=400, detail="Empty JPEG scan data.")

        if not (seen_sof and seen_sos and seen_eoi) or pos != n:
            raise HTTPException(status_code=400, detail="Truncated or corrupt JPEG image.")

    @staticmethod
    def _verify_webp(data: bytes, max_dimension: int, max_pixels: int) -> None:
        if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise HTTPException(status_code=400, detail="Corrupt or truncated WebP image.")

        riff_size = struct.unpack("<I", data[4:8])[0]
        if 8 + riff_size != len(data):
            raise HTTPException(status_code=400, detail="Truncated or malformed WebP container.")

        pos = 12
        n = len(data)
        checked_dimensions = False
        seen_bitstream = False

        while pos < n:
            if pos + 8 > n:
                raise HTTPException(status_code=400, detail="Truncated WebP chunk header.")
            fourcc = data[pos:pos + 4]
            chunk_size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
            chunk_start = pos + 8
            chunk_end = chunk_start + chunk_size
            if chunk_end > n:
                raise HTTPException(status_code=400, detail="Truncated WebP chunk payload.")
            chunk = data[chunk_start:chunk_end]
            padded_end = chunk_end + (chunk_size & 1)
            if padded_end > n:
                raise HTTPException(status_code=400, detail="Malformed WebP chunk padding.")
            pos = padded_end

            if fourcc == b"VP8X":
                if chunk_size != 10:
                    raise HTTPException(status_code=400, detail="Invalid VP8X header.")
                width = int.from_bytes(chunk[4:7], "little") + 1
                height = int.from_bytes(chunk[7:10], "little") + 1
                UploadService._check_dimensions(width, height, max_dimension, max_pixels)
                checked_dimensions = True
            elif fourcc == b"VP8 ":
                if chunk_size < 10 or (chunk[0] & 0x01) != 0 or chunk[3:6] != b"\x9d\x01\x2a":
                    raise HTTPException(status_code=400, detail="Invalid lossy WebP frame header.")
                first_part_len = (chunk[0] | (chunk[1] << 8) | (chunk[2] << 16)) >> 5
                if 10 + first_part_len > chunk_size:
                    raise HTTPException(status_code=400, detail="Truncated lossy WebP partition.")
                width = struct.unpack("<H", chunk[6:8])[0] & 0x3FFF
                height = struct.unpack("<H", chunk[8:10])[0] & 0x3FFF
                UploadService._check_dimensions(width, height, max_dimension, max_pixels)
                checked_dimensions = True
                seen_bitstream = True
            elif fourcc == b"VP8L":
                if chunk_size < 5 or chunk[0] != 0x2F:
                    raise HTTPException(status_code=400, detail="Invalid lossless WebP header.")
                bits = struct.unpack("<I", chunk[1:5])[0]
                version = (bits >> 29) & 0x07
                if version != 0:
                    raise HTTPException(status_code=400, detail="Unsupported lossless WebP version.")
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
                UploadService._check_dimensions(width, height, max_dimension, max_pixels)
                checked_dimensions = True
                seen_bitstream = True
            elif fourcc == b"ANMF" and chunk_size >= 16:
                seen_bitstream = True

        if not (checked_dimensions and seen_bitstream) or pos != n:
            raise HTTPException(status_code=400, detail="Incomplete or corrupt WebP image.")

    @staticmethod
    def _atomic_store_bytes(data: bytes, canonical_ext: str) -> str:
        base_dir = (Path(settings.UPLOAD_DIR).resolve() / "products").resolve()
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
