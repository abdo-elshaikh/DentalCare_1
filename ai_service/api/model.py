"""Model loading and inference utilities.

Uses the unified :class:`CephalometricHRNet` from ``training.model``.
"""

import os
import sys

import torch

# Ensure project root is on sys.path so ``training.model`` can be imported
# regardless of which entry-point starts the application.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from training.model import CephalometricHRNet


def load_model(weights_path: str = "../models/best_model.pth") -> CephalometricHRNet:
    """Load a trained HRNet model from a checkpoint file.

    The function auto-detects:
    * Whether the checkpoint is a dual-head (offset) or single-head model.
    * The number of landmarks stored in the checkpoint.
    """
    print("Loading HRNet model...")
    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

    state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
    if "model_state_dict" in state_dict:
        state_dict = state_dict["model_state_dict"]

    # ── Auto-detect architecture from checkpoint keys ─────────────
    has_offset_head = False
    num_landmarks = 19  # default

    for k, v in state_dict.items():
        if "offset_head" in k:
            has_offset_head = True
        if k.endswith("final_layer.weight") or k == "final_layer.weight":
            num_landmarks = v.shape[0]
        elif k.endswith("heatmap_head.3.weight") or k == "heatmap_head.3.weight":
            num_landmarks = v.shape[0]

    print(
        f"Inferred {num_landmarks} landmarks from model weights. "
        f"Dual-head (offset regression): {has_offset_head}"
    )

    model = CephalometricHRNet(
        num_landmarks=num_landmarks,
        backbone="hrnet_w32",
        pretrained=False,
        has_offset_head=has_offset_head,
    )

    # ── Map state_dict keys to our unified model ──────────────────
    new_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith(("backbone.", "final_layer.", "heatmap_head.", "offset_head.")):
            new_state_dict[k] = v
        elif k == "temperature":
            new_state_dict[k] = v
        else:
            # Legacy checkpoints may omit the 'backbone.' prefix
            new_state_dict["backbone." + k] = v

    load_result = model.load_state_dict(new_state_dict, strict=False)

    # Determine which heads are expected to be missing
    allowed_missing_prefixes = (
        ["final_layer."] if has_offset_head else ["heatmap_head.", "offset_head."]
    )
    unexpected_missing = [
        key
        for key in load_result.missing_keys
        if key != "temperature"
        and not any(key.startswith(pfx) for pfx in allowed_missing_prefixes)
    ]

    if load_result.unexpected_keys or unexpected_missing:
        raise RuntimeError(
            "Checkpoint/model mismatch: "
            f"unexpected_keys={load_result.unexpected_keys}, "
            f"missing_keys={unexpected_missing}"
        )

    model.eval()
    return model


def run_inference(
    model: CephalometricHRNet, image_tensor: torch.Tensor
):
    """Run inference on a preprocessed image tensor.

    Returns ``(heatmaps, offsets)`` for dual-head models,
    or ``(heatmaps, None)`` for single-head models.
    """
    with torch.no_grad():
        if getattr(model, "has_offset_head", False):
            heatmaps, offsets = model(image_tensor)
            return heatmaps, offsets
        else:
            heatmaps = model(image_tensor)
            return heatmaps, None