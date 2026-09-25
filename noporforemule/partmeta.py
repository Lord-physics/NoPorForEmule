"""Read the filename tag from an eMule-compatible .part.met file."""

from __future__ import annotations

from pathlib import Path

MAX_MET_BYTES = 4 * 1024 * 1024


def download_name(part: Path) -> str | None:
    met = part.with_name(part.name + ".met")
    try:
        if met.stat().st_size > MAX_MET_BYTES:
            return None
        data = met.read_bytes()
        if not data or data[0] not in (0xE0, 0xE1, 0xE2):
            return None
        position = 21  # version, date and MD4 hash

        def take(length: int) -> bytes:
            nonlocal position
            if length < 0 or position + length > len(data):
                raise ValueError("truncated metadata")
            value = data[position:position + length]
            position += length
            return value

        hashes = int.from_bytes(take(2), "little")
        take(hashes * 16)
        tags = int.from_bytes(take(4), "little")
        if tags > 10000:
            return None
        for _ in range(tags):
            kind = take(1)[0]
            if kind & 0x80:  # eMule compact tag: one-byte name follows
                kind &= 0x7F
                name = take(1)
            else:
                name = take(int.from_bytes(take(2), "little"))
            if kind == 0x02 or 0x11 <= kind <= 0x20:
                length = int.from_bytes(take(2), "little") if kind == 0x02 else kind - 0x10
                value = take(length)
                if name == b"\x01":
                    try:
                        decoded = value.decode("utf-8")
                    except UnicodeDecodeError:
                        decoded = value.decode("cp1252", errors="replace")
                    # Show a name, never let metadata masquerade as a path.
                    return Path(decoded.replace("\\", "/")).name[:255] or None
            elif kind in (0x01, 0x03, 0x04, 0x05, 0x08, 0x09, 0x0B):
                take({0x01: 16, 0x03: 4, 0x04: 4, 0x05: 1, 0x08: 2, 0x09: 1, 0x0B: 8}[kind])
            elif kind in (0x06, 0x0A):
                length = int.from_bytes(take(2), "little")
                take(length // 8 + 1 if kind == 0x06 else length)
            elif kind == 0x07:
                take(int.from_bytes(take(4), "little"))
            else:
                return None
    except (OSError, ValueError):
        return None
    return None
