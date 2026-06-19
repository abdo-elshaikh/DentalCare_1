from io import BytesIO

import pytest
import torch
from PIL import Image

from api.xray_validator import XrayValidator


class ConstantClassifier(torch.nn.Module):
    def __init__(self, logits):
        super().__init__()
        self.register_buffer("constant_logits", torch.tensor(logits, dtype=torch.float32))

    def forward(self, image):
        return self.constant_logits.unsqueeze(0).expand(image.shape[0], -1)


def _validator(tmp_path, logits):
    model = ConstantClassifier(logits).eval()
    traced = torch.jit.trace(model, torch.zeros(1, 3, 224, 224))
    model_path = tmp_path / "validator.pt"
    traced.save(str(model_path))
    return XrayValidator(model_path)


def _image_bytes(size=(300, 300)):
    output = BytesIO()
    Image.new("L", size, color=80).save(output, format="PNG")
    return output.getvalue()


def test_accepts_high_confidence_lateral_ceph(tmp_path):
    result = _validator(tmp_path, [10.0, 0.0, 0.0]).validate(_image_bytes())

    assert result["accepted"] is True
    assert result["label"] == "lateral_ceph"
    assert result["reason"] is None


@pytest.mark.parametrize(
    ("logits", "expected_label"),
    [([0.0, 10.0, 0.0], "other_xray"), ([0.0, 0.0, 10.0], "non_xray")],
)
def test_rejects_non_cephalometric_classes(tmp_path, logits, expected_label):
    result = _validator(tmp_path, logits).validate(_image_bytes())

    assert result["accepted"] is False
    assert result["label"] == expected_label


def test_rejects_invalid_image_bytes(tmp_path):
    result = _validator(tmp_path, [10.0, 0.0, 0.0]).validate(b"not an image")

    assert result["accepted"] is False
    assert result["label"] == "invalid_image"


def test_rejects_low_resolution_image(tmp_path):
    result = _validator(tmp_path, [10.0, 0.0, 0.0]).validate(_image_bytes((100, 100)))

    assert result["accepted"] is False
    assert result["label"] == "invalid_image"
