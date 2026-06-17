import torch
import torch.nn as nn
import timm


class CephalometricHRNet(nn.Module):
    """Unified HRNet model for cephalometric landmark detection.

    Supports two modes controlled by ``has_offset_head``:
      • **Single-head** (``has_offset_head=False``): returns only heatmaps.
        Uses a lightweight ``final_layer`` (1×1 conv).
      • **Dual-head** (``has_offset_head=True``): returns (heatmaps, offsets).
        Uses deeper ``heatmap_head`` and ``offset_head`` with BN+ReLU.

    """

    def __init__(
        self,
        num_landmarks: int = 19,
        backbone: str = "hrnet_w32",
        pretrained: bool = True,
        has_offset_head: bool = True,
    ):
        super().__init__()
        self.num_landmarks = num_landmarks
        self.has_offset_head = has_offset_head

        # ── Backbone ──────────────────────────────────────────────────
        self.backbone = timm.create_model(backbone, pretrained=pretrained)

        # Strip classification head components safely
        self.backbone.incre_modules = nn.Identity()
        self.backbone.downsamp_modules = nn.Identity()
        self.backbone.global_pool = nn.Identity()
        self.backbone.classifier = nn.Identity()
        self.backbone.final_layer = nn.Identity()

        # Dynamically detect the number of channels from the backbone
        # rather than relying on fragile backbone-name string matching.
        try:
            in_channels = self.backbone.feature_info.channels()[0]
        except (AttributeError, IndexError):
            # Fallback: infer from backbone name if feature_info unavailable
            _width_map = {"hrnet_w18": 18, "hrnet_w32": 32, "hrnet_w48": 48}
            in_channels = _width_map.get(backbone, 32)

        self._in_channels = in_channels

        # ── Heatmap prediction (single-head path) ────────────────────
        self.final_layer = nn.Conv2d(
            in_channels, num_landmarks, kernel_size=1, stride=1, padding=0
        )

        # ── Heatmap prediction (dual-head path) ──────────────────────
        self.heatmap_head = nn.Sequential(
            nn.Conv2d(in_channels, in_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels, num_landmarks, kernel_size=1),
        )

        # ── Coordinate offset prediction head ────────────────────────
        self.offset_head = nn.Sequential(
            nn.Conv2d(in_channels, in_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels, num_landmarks * 2, kernel_size=1),
        )

        # ── Temperature (non-learnable by default, calibrated post-training) ──
        self.register_buffer("temperature", torch.ones(1) * 1.35)

    def make_temperature_learnable(self):
        """Convert temperature buffer to a learnable Parameter (for calibration)."""
        val = self.temperature.clone()
        del self.temperature
        self.temperature = nn.Parameter(val)

    def _forward_high_res_features(self, x: torch.Tensor) -> torch.Tensor:
        """Run HRNet stages and return the highest-resolution branch feature map."""
        x = self.backbone.conv1(x)
        x = self.backbone.bn1(x)
        x = self.backbone.act1(x)
        x = self.backbone.conv2(x)
        x = self.backbone.bn2(x)
        x = self.backbone.act2(x)
        x = self.backbone.layer1(x)

        def _apply_transition(transition, prev_list):
            out = []
            for i, trans in enumerate(transition):
                src = prev_list[i] if i < len(prev_list) else prev_list[-1]
                out.append(trans(src) if trans is not None else src)
            return out

        y_list = _apply_transition(self.backbone.transition1, [x])
        y_list = self.backbone.stage2(y_list)
        y_list = _apply_transition(self.backbone.transition2, y_list)
        y_list = self.backbone.stage3(y_list)
        y_list = _apply_transition(self.backbone.transition3, y_list)
        y_list = self.backbone.stage4(y_list)

        return y_list[0]

    def forward(self, x):
        high_res_features = self._forward_high_res_features(x)

        if self.has_offset_head:
            heatmaps = self.heatmap_head(high_res_features) / self.temperature
            offsets = self.offset_head(high_res_features)
            return heatmaps, offsets
        else:
            heatmaps = self.final_layer(high_res_features) / self.temperature
            return heatmaps


# ── Backward-compatible alias ─────────────────────────────────────────
# So existing code that does `from .model import AdvancedHRNetKeypointDetector`
# continues to work without changes.
HRNetKeypointDetector = CephalometricHRNet
