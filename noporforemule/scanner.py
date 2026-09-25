from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".mpg", ".mpeg"}
ALERT_LABELS = {
    "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "ANUS_EXPOSED",
    "FEMALE_BREAST_EXPOSED", "BUTTOCKS_EXPOSED",
}
MODEL_VERSION = "nudenet-3.4.0-320n-0.45-v2"
MAX_PART_IMAGE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class ScanResult:
    status: str  # possible, clear, unscanned
    detail: str


class VisualScanner:
    """One local CPU detector, loaded only when a supported file is scanned."""

    def __init__(self) -> None:
        self._detector = None

    def _detect(self, frame) -> bool:
        if self._detector is None:
            from nudenet import NudeDetector
            self._detector = NudeDetector()
        detections = self._detector.detect(frame)
        return any(
            item.get("class") in ALERT_LABELS and item.get("score", 0) >= 0.45
            for item in detections
        )

    def scan(self, path: Path) -> ScanResult:
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            return ScanResult("unscanned", "Formato no compatible")
        try:
            import cv2
            if suffix in IMAGE_EXTENSIONS:
                # imdecode accepts Windows paths containing non-ASCII characters.
                import numpy as np
                frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    return ScanResult("unscanned", "Imagen dañada o ilegible")
                found = self._detect(frame)
                return ScanResult("possible" if found else "clear", "Imagen analizada")

            return self._scan_video(path, partial=False)
        except Exception as exc:
            return ScanResult("unscanned", f"Error de análisis: {type(exc).__name__}")

    def scan_part(self, path: Path) -> ScanResult:
        """Look for decodable content in an eMule part without modifying it."""
        try:
            with path.open("rb") as source:
                header = source.read(16)
            image = (header.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"BM"))
                     or header[:4] in (b"II*\x00", b"MM\x00*")
                     or header[:4] == b"RIFF" and header[8:12] == b"WEBP")
            video = (header[:4] == b"RIFF" and header[8:12] == b"AVI "
                     or header[4:8] == b"ftyp"
                     or header.startswith(b"\x1a\x45\xdf\xa3")
                     or header.startswith(bytes.fromhex("3026b2758e66cf11")))
            if image:
                if path.stat().st_size > MAX_PART_IMAGE_BYTES:
                    return ScanResult("unscanned", "Imagen temporal demasiado grande para lectura segura")
                import cv2
                import numpy as np
                frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    return ScanResult("unscanned", "Imagen aún incompleta o ilegible")
                return (ScanResult("possible", "Indicio en la imagen temporal") if self._detect(frame)
                        else ScanResult("unscanned", "Sin indicios en lo legible; descarga incompleta"))
            if video:
                return self._scan_video(path, partial=True)
            return ScanResult("unscanned", "Aún no hay cabecera reconocible en el archivo temporal")
        except Exception as exc:
            return ScanResult("unscanned", f"No se pudo leer el temporal: {type(exc).__name__}")

    def _scan_video(self, path: Path, partial: bool) -> ScanResult:
        import cv2
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return ScanResult("unscanned", "Vídeo incompleto, dañado o no compatible")
        try:
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if total <= 0:
                return ScanResult("unscanned", "No se pudo determinar la duración")
            sampled = 0
            for fraction in (0.05, 0.25, 0.5, 0.75, 0.95):
                capture.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(total * fraction)))
                ok, frame = capture.read()
                if not ok:
                    continue
                sampled += 1
                if self._detect(frame):
                    return ScanResult("possible", f"Indicio en {sampled} fotograma(s) analizados")
            if sampled == 0:
                return ScanResult("unscanned", "No se pudieron leer fotogramas")
            if partial:
                return ScanResult("unscanned", f"Sin indicios en {sampled} fotograma(s); descarga incompleta")
            return ScanResult("clear", f"{sampled} fotograma(s) analizados")
        finally:
            capture.release()
