import queue
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import cv2
import numpy as np

from noporforemule.app import confirm_and_open
from noporforemule.monitor import Monitor
from noporforemule.partmeta import download_name
from noporforemule.scanner import ScanResult, VisualScanner
from noporforemule.storage import Cache
from noporforemule.startup import set_startup, startup_enabled


class AppTests(unittest.TestCase):
    def test_open_requires_confirmation_for_all_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.jpg"
            path.write_bytes(b"x")
            for state in ("possible", "clear", "unscanned"):
                ask, opener = Mock(return_value=False), Mock()
                self.assertFalse(confirm_and_open(path, ScanResult(state, ""), ask, opener))
                opener.assert_not_called()
                ask.return_value = True
                self.assertTrue(confirm_and_open(path, ScanResult(state, ""), ask, opener))
                opener.assert_called_once_with(str(path))

    def test_real_detector_and_broken_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            scanner = VisualScanner()
            clean = Path(tmp) / "blank.png"
            cv2.imwrite(str(clean), np.zeros((320, 320, 3), dtype=np.uint8))
            self.assertEqual(scanner.scan(clean).status, "clear")
            broken = Path(tmp) / "broken.png"
            broken.write_bytes(b"not an image")
            self.assertEqual(scanner.scan(broken).status, "unscanned")
            self.assertEqual(scanner.scan(Path(tmp) / "unsupported.txt").status, "unscanned")

    def test_real_video_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5, (320, 320))
            self.assertTrue(writer.isOpened())
            for _ in range(10):
                writer.write(np.zeros((320, 320, 3), dtype=np.uint8))
            writer.release()
            result = VisualScanner().scan(path)
            self.assertEqual(result.status, "clear")
            self.assertIn("fotograma", result.detail)

    def test_part_is_read_before_completion_but_never_marked_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "001.part"
            cv2.imwrite(str(Path(tmp) / "image.png"), np.zeros((320, 320, 3), dtype=np.uint8))
            path.write_bytes((Path(tmp) / "image.png").read_bytes())
            result = VisualScanner().scan_part(path)
            self.assertEqual(result.status, "unscanned")
            self.assertIn("descarga incompleta", result.detail)
            path.write_bytes(b"\x00" * 64)
            self.assertEqual(VisualScanner().scan_part(path).status, "unscanned")

    def test_part_metadata_resolves_download_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "001.part"
            part.write_bytes(b"")
            name = "película de prueba.mp4".encode("utf-8")
            header = b"\xe0" + b"\x00" * 20 + struct.pack("<H", 0) + struct.pack("<I", 1)
            tag = b"\x02" + struct.pack("<H", 1) + b"\x01" + struct.pack("<H", len(name)) + name
            part.with_name("001.part.met").write_bytes(header + tag)
            self.assertEqual(download_name(part), "película de prueba.mp4")
            compact = b"\x82\x01" + struct.pack("<H", len(name)) + name
            part.with_name("001.part.met").write_bytes(header + compact)
            self.assertEqual(download_name(part), "película de prueba.mp4")

    def test_monitor_waits_for_stability_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Incoming"
            folder.mkdir()
            path = folder / "clip.jpg"
            path.write_bytes(b"image")
            fake = Mock()
            fake.scan.return_value = ScanResult("clear", "Analizado")
            events = queue.Queue()
            monitor = Monitor(root / "state", events, fake)
            monitor.incoming = folder
            cache = Cache(root / "state")
            try:
                monitor.poll_once(cache)
                fake.scan.assert_not_called()
                monitor.poll_once(cache)
                fake.scan.assert_called_once_with(path)
                monitor.poll_once(cache)
                fake.scan.assert_called_once()
                path.write_bytes(b"changed image")
                monitor.poll_once(cache)
                fake.scan.assert_called_once()
                monitor.poll_once(cache)
                self.assertEqual(fake.scan.call_count, 2)
            finally:
                cache.close()

    def test_temp_monitor_reports_positive_without_waiting_for_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp = root / "Temp"
            temp.mkdir()
            part = temp / "001.part"
            part.write_bytes(b"partial")
            fake = Mock()
            fake.scan_part.return_value = ScanResult("possible", "Indicio")
            events = queue.Queue()
            monitor = Monitor(root / "state", events, fake)
            monitor.temp = temp
            cache = Cache(root / "state")
            try:
                monitor.poll_once(cache)
                fake.scan_part.assert_called_once_with(part)
                self.assertTrue(any(item[0] == "result" and item[2].status == "possible"
                                    for item in list(events.queue)))
                part.write_bytes(b"partial changed")
                monitor.poll_once(cache)
                fake.scan_part.assert_called_once()
                self.assertIn(part, monitor._flagged_parts)
            finally:
                cache.close()

    def test_startup_shortcut_can_be_enabled_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "IniciarConEmule.bat"
            target.write_text("@echo off", encoding="ascii")
            with patch.dict("os.environ", {"APPDATA": tmp}):
                set_startup(target, True)
                self.assertTrue(startup_enabled(target))
                set_startup(target, False)
                self.assertFalse(startup_enabled(target))


if __name__ == "__main__":
    unittest.main()
