from __future__ import annotations

import threading
import time
from pathlib import Path
from queue import Queue

from .scanner import ScanResult, VisualScanner
from .storage import Cache

IGNORED_SUFFIXES = {".met", ".tmp", ".temp", ".crdownload"}
PART_SCAN_INTERVAL = 30


class Monitor:
    def __init__(self, base: Path, events: Queue, scanner: VisualScanner | None = None):
        self.base = base
        self.events = events
        self.scanner = scanner or VisualScanner()
        self.incoming: Path | None = None
        self.temp: Path | None = None
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._observed: dict[Path, tuple[int, int]] = {}
        self._last_part_scan: dict[Path, float] = {}
        self._flagged_parts: set[Path] = set()

    def start(self, incoming: Path | None, temp: Path | None) -> None:
        self.stop()
        self.incoming = incoming
        self.temp = temp
        self.stop_event = threading.Event()
        self._observed = {}
        self._last_part_scan = {}
        self._flagged_parts = set()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=2)

    def _run(self) -> None:
        cache = Cache(self.base)
        try:
            while not self.stop_event.is_set():
                self.poll_once(cache)
                self.stop_event.wait(3)
        finally:
            cache.close()

    def poll_once(self, cache: Cache) -> None:
        folders = [(folder, kind) for folder, kind in ((self.incoming, "incoming"), (self.temp, "temp")) if folder]
        seen = set()
        for folder, kind in folders:
            if not folder.is_dir():
                self.events.put(("message", f"Carpeta {kind} no disponible"))
                continue
            try:
                paths = list(folder.iterdir())
            except OSError:
                self.events.put(("message", f"No se puede leer la carpeta {kind}"))
                continue
            for path in paths:
                if self.stop_event.is_set():
                    break
                part = kind == "temp" and path.suffix.lower() == ".part"
                if (kind == "temp" and not part) or (kind == "incoming" and path.suffix.lower() in IGNORED_SUFFIXES | {".part"}) or not path.is_file():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                seen.add(path)
                signature = (stat.st_size, stat.st_mtime_ns)
                prior = self._observed.get(path)
                self._observed[path] = signature
                if part and path in self._flagged_parts:
                    self.events.put(("result", path, ScanResult("possible", "Indicio detectado durante la descarga")))
                    continue
                cached = cache.get(path, *signature)
                if cached:
                    if part and cached.status == "possible":
                        self._flagged_parts.add(path)
                    self.events.put(("result", path, cached))
                    continue
                if part and time.monotonic() - self._last_part_scan.get(path, float("-inf")) < PART_SCAN_INTERVAL:
                    self.events.put(("result", path, ScanResult("unscanned", "Esperando siguiente revisión del temporal")))
                    continue
                if not part and prior != signature:
                    self.events.put(("result", path, ScanResult("unscanned", "Esperando a que termine de cambiar")))
                    continue
                self.events.put(("result", path, ScanResult("unscanned", "Analizando…")))
                if part:
                    self._last_part_scan[path] = time.monotonic()
                result = self.scanner.scan_part(path) if part else self.scanner.scan(path)
                try:
                    after = path.stat()
                    if (after.st_size, after.st_mtime_ns) != signature:
                        if result.status != "possible":
                            result = ScanResult("unscanned", "El archivo cambió durante el análisis")
                    else:
                        cache.put(path, *signature, result)
                except OSError:
                    if result.status != "possible":
                        result = ScanResult("unscanned", "Archivo inaccesible")
                if part and result.status == "possible":
                    self._flagged_parts.add(path)
                self.events.put(("result", path, result))
        for missing in self._observed.keys() - seen:
            self._observed.pop(missing, None)
            self._last_part_scan.pop(missing, None)
            self._flagged_parts.discard(missing)
            self.events.put(("remove", missing))
