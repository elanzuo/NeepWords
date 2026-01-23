from PIL import Image

from neepwordextractor import ocr_engine


class _FakeOCR:
    last_kwargs = None
    last_unit = None

    def __init__(self, image, **kwargs):
        self.image = image
        self.kwargs = kwargs
        _FakeOCR.last_kwargs = kwargs
        self.unit = None

    def recognize(self, unit=None):
        self.unit = unit
        _FakeOCR.last_unit = unit
        return [
            ("alpha", 0.91, (0, 0, 10, 10)),
            ("beta", 0.88, (10, 0, 20, 10)),
        ]


class _FakeModule:
    OCR = _FakeOCR


def test_run_ocr_normalizes_results(monkeypatch):
    def _fake_loader():
        return _FakeModule

    monkeypatch.setattr(ocr_engine, "_load_ocrmac", _fake_loader)

    image = Image.new("RGB", (10, 10))
    annotations = ocr_engine.run_ocr(image, recognition_level="fast")
    assert len(annotations) == 2
    assert annotations[0].text == "alpha"
    assert annotations[0].confidence == 0.91
    assert annotations[0].bbox == (0, 0, 10, 10)
    assert _FakeOCR.last_kwargs is not None
    assert _FakeOCR.last_kwargs["recognition_level"] == "fast"


def test_run_ocr_passes_unit(monkeypatch):
    def _fake_loader():
        return _FakeModule

    monkeypatch.setattr(ocr_engine, "_load_ocrmac", _fake_loader)

    image = Image.new("RGB", (10, 10))
    annotations = ocr_engine.run_ocr(image, unit="line")
    assert annotations[0].text == "alpha"
    assert _FakeOCR.last_unit == "line"


def test_run_ocr_livetext_omits_recognition_level(monkeypatch):
    def _fake_loader():
        return _FakeModule

    monkeypatch.setattr(ocr_engine, "_load_ocrmac", _fake_loader)

    image = Image.new("RGB", (10, 10))
    ocr_engine.run_ocr(image, framework="livetext")
    assert _FakeOCR.last_kwargs is not None
    assert "recognition_level" not in _FakeOCR.last_kwargs
