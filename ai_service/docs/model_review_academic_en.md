# Technical and Academic Review of the Cephalometric Landmark Detection Model

## Executive Summary

This project is an AI-assisted cephalometric analysis platform. Its central machine-learning component is an HRNet-based landmark detector that predicts 19 anatomical landmarks on lateral cephalometric radiographs. Around that detector, the repository adds preprocessing, heatmap post-processing, optional sub-pixel offset refinement, anatomical validation, cephalometric measurement computation, protocol-based normative comparison, diagnosis generation, treatment suggestions, and report output.

The most important point is that the system is not a single monolithic "diagnostic AI model." It is a layered pipeline:

1. A deep-learning landmark localization model.
2. Deterministic geometry for angles, distances, and ratios.
3. Norm-based clinical classification using reference means and standard deviations.
4. Rule-based diagnostic and treatment reasoning.
5. UI and API layers for clinical workflow.

The model choice is appropriate for landmark detection because HRNet preserves high-resolution spatial features, which is essential in cephalometry where small localization errors can materially change angular measurements such as SNA, SNB, ANB, FMA, IMPA, and SN-GoGn.

## 1. Repository-Level Architecture

The operational workflow is distributed across several modules:

| Layer | Main files | Role |
|---|---|---|
| Model definition | `api/model.py`, `training/model.py` | HRNet landmark detector wrappers |
| Training | `training/train.py`, `training/dataset.py`, `training/loss.py` | Dataset loading, augmentation, target heatmaps, offset targets, loss, optimizer |
| Inference utilities | `api/utils.py` | Image preprocessing, heatmap decoding, offset refinement, landmark validation |
| Measurements | `api/analysis.py`, `api/measurements.py` | Geometric cephalometric measurements and uncertainty estimation |
| Protocols and norms | `api/protocols.py`, `api/norms.py`, `references/*.json` | Steiner, Tweed, Downs, McNamara, Jarabak, Eastman, ABO-style reference mappings |
| Diagnosis | `api/diagnostic_engine.py` | Skeletal class, vertical pattern, severity, craniofacial pattern, ICD-10 suggestions |
| Treatment reasoning | `api/treatment_engine.py` | Rule-based treatment-plan suggestions |
| API | `api/main.py` | Stateless FastAPI endpoints for detection, measurements, diagnosis, reports, and overlays |
| UI | `ui/*` | Streamlit clinical workspace |

This separation is generally strong: model inference is kept distinct from clinical interpretation. That is important because landmark detection uncertainty and diagnostic reasoning have different failure modes.

## 2. Primary Model Used

### 2.1 Production Detector: `HRNetKeypointDetector`

The deployed model in `api/model.py` is `HRNetKeypointDetector`. It uses:

- Backbone: `timm.create_model("hrnet_w32", pretrained=False)`.
- Output landmark count: inferred from checkpoint weights, defaulting to 19.
- Heatmap-only mode: a single `1x1` convolution called `final_layer`.
- Dual-head mode: a richer `heatmap_head` plus `offset_head`.
- Temperature calibration: learnable scalar initialized to `1.35`.

The current deployed checkpoint, `models/best_model.pth`, is a heatmap-only checkpoint. It contains `final_layer.weight` with shape `(19, 32, 1, 1)` and does not contain `offset_head` or `heatmap_head.3.weight` keys. Therefore, the production runtime currently performs heatmap-only landmark localization, while the dual-head offset path remains supported by code but inactive for this checkpoint.

The model removes classification-specific HRNet layers:

- `incre_modules = None`
- `downsamp_modules = None`
- `global_pool = nn.Identity()`
- `classifier = nn.Identity()`
- `final_layer = nn.Identity()` on the timm backbone

The forward pass uses the first HRNet feature branch:

```python
features = self.backbone.forward_features(x)
high_res_features = features[0]
```

For HRNet-W32, this branch has 32 channels and remains at high spatial resolution. With a 768 x 768 input, the produced heatmap is typically 192 x 192, corresponding to a stride of 4 pixels.

### 2.2 Training Detector: `AdvancedHRNetKeypointDetector`

The training model in `training/model.py` is more flexible. It supports:

- `hrnet_w32`
- `hrnet_w48`
- `hrnet_w18`

It always uses a dual-head output:

1. `heatmap_head`: predicts one heatmap per landmark.
2. `offset_head`: predicts two offset channels per landmark, one for x and one for y.

The heatmap head structure is:

```text
Conv2d(in_channels -> in_channels, 3x3, padding=1)
BatchNorm2d
ReLU
Conv2d(in_channels -> num_landmarks, 1x1)
```

The offset head has the same structure but outputs `num_landmarks * 2` channels.

### 2.3 Difference Between Production and Training Model Wrappers

| Attribute | Production `api/model.py` | Training `training/model.py` |
|---|---|---|
| Backbone | Fixed HRNet-W32 | HRNet-W18/W32/W48 |
| Pretraining flag | `pretrained=False` | `pretrained=True` |
| Output mode | Heatmap-only or dual-head based on checkpoint | Always dual-head |
| Landmark count | Inferred from checkpoint, default 19 | Constructor argument, default 19 |
| State loading | `strict=False` | Trained directly |
| Main purpose | Robust service loading | Research/training flexibility |

This is practical, but it creates a maintenance risk: training and production are not exactly the same class. Checkpoints are mapped into the production wrapper with flexible key handling and `strict=False`, which helps compatibility but may hide missing or mismatched weights.

## 3. Key Model Attributes

| Attribute | Value / Behavior | Significance |
|---|---|---|
| Architecture family | HRNet | Preserves spatial detail better than simple encoder-decoder downsampling |
| Main variant | HRNet-W32 | Balanced accuracy and compute cost |
| Alternative variants | HRNet-W18, HRNet-W48 | W18 is lighter; W48 is heavier and potentially more accurate |
| Input size | 768 x 768 | Standardized model input |
| Heatmap size | Usually 192 x 192 | Stride-4 representation |
| Number of landmarks | 19 | Canonical lateral cephalometric landmark set |
| Heatmap channels | 19 | One likelihood map per landmark |
| Offset channels | 38 when enabled; absent from current checkpoint | x/y refinement per landmark |
| Temperature | Initialized to 1.35; not present in current checkpoint state | Calibrates heatmap logits |
| Output confidence | Heatmap maximum value | Used as landmark score |
| Checkpoint | `models/best_model.pth` | Single production weight source |

## 4. Landmark Set

The 19 landmarks are defined in `shared/landmarks.py`:

| ID | Landmark |
|---:|---|
| 1 | Sella (S) |
| 2 | Nasion (N) |
| 3 | Orbitale (Or) |
| 4 | Porion (Po) |
| 5 | Subspinale / A-point |
| 6 | Supramentale / B-point |
| 7 | Pogonion (Pog) |
| 8 | Menton (Me) |
| 9 | Gnathion (Gn) |
| 10 | Gonion (Go) |
| 11 | Lower Incisor Tip (LIT) |
| 12 | Upper Incisor Tip (UIT) |
| 13 | Upper Lip (UL) |
| 14 | Lower Lip (LL) |
| 15 | Subnasale (Sn) |
| 16 | Soft Tissue Pogonion (Pog') |
| 17 | Posterior Nasal Spine (PNS) |
| 18 | Anterior Nasal Spine (ANS) |
| 19 | Articulare (Ar) |

The fixed 19-point design is enough for core lateral cephalometric analysis, but not enough for every measurement in full commercial cephalometric systems. The protocol layer correctly handles this by validating which measurements are computable from available landmark IDs.

## 5. Input Features and Preprocessing

The neural model uses the radiograph image itself as the input feature source. No handcrafted image features are passed into the CNN.

In `api/utils.py`, preprocessing performs:

1. Decode uploaded image bytes using OpenCV.
2. Convert BGR to RGB.
3. Store original image size for later coordinate remapping.
4. Resize to 768 x 768.
5. Normalize using ImageNet statistics:
   - mean: `[0.485, 0.456, 0.406]`
   - standard deviation: `[0.229, 0.224, 0.225]`
6. Convert to PyTorch tensor with shape `[1, 3, 768, 768]`.

Training preprocessing in `training/dataset.py` uses Albumentations:

- Resize to 768 x 768.
- ImageNet normalization.
- Tensor conversion.
- Optional CLAHE.
- Random brightness and contrast.
- Random gamma.
- Shift, scale, and rotation.
- Coarse dropout.

Horizontal flipping is intentionally avoided because lateral cephalograms are anatomically directional; flipping would swap clinical orientation and corrupt the meaning of several landmarks.

## 6. Output Representation

The model uses heatmap-based localization rather than direct coordinate regression.

### 6.1 Heatmaps

Each landmark has a separate heatmap. The strongest point in the heatmap is interpreted as the predicted landmark position. This is decoded in `get_max_preds()` by flattening each heatmap and taking `argmax`.

Advantages:

- Preserves spatial uncertainty.
- Works well for point localization.
- More stable than directly predicting raw x/y coordinates.
- Allows per-landmark confidence using the heatmap peak.

Limitations:

- The coordinate is initially restricted to the heatmap grid.
- With a 192 x 192 heatmap, one heatmap cell corresponds to roughly 4 pixels in the 768 x 768 input.

### 6.2 Offset Regression

When the checkpoint contains an offset head, the model predicts sub-cell offsets:

- `offset_head` output shape: `[batch, 38, H, W]`
- For landmark `i`:
  - channel `2*i` stores x offset.
  - channel `2*i + 1` stores y offset.

During post-processing, the code reads the offset at the heatmap peak and adds it to the discrete coordinate before mapping back to the original image size. This improves precision beyond the stride-4 grid.

In the currently deployed checkpoint, this path is not active because no `offset_head` weights are present. The practical implication is that final predictions are limited by heatmap peak resolution and original-image scaling unless a separate local refinement step is applied.

### 6.3 Temperature Calibration

Both model wrappers divide heatmap logits by a learnable temperature parameter:

```python
heatmaps = self.heatmap_head(high_res_features) / self.temperature
```

The initial value is `1.35`. Larger temperature values soften logits; smaller values sharpen them. In practice, this can influence peak sharpness and confidence calibration. The repository also includes `training/calibrate_temperature.py`, indicating that calibration is treated as a distinct concern.

## 7. Training Configuration

The training script in `training/train.py` uses:

| Parameter | Script value |
|---|---:|
| Input size | 768 x 768 |
| Feature/heatmap size | input divided by 4 |
| Number of landmarks | 19 |
| Batch size | 4 |
| Epochs | 10 |
| Optimizer | AdamW |
| Learning rate | 1e-4 |
| Weight decay | 1e-4 |
| Heatmap loss weight | 1.0 |
| Offset loss weight | 0.1 |
| Target heatmap sigma | 2.0 |

The `models/config.yaml` file describes a more ambitious configuration:

- 400 epochs.
- Gradient accumulation of 4.
- Effective batch size of 16.
- Weight decay of 0.01.
- Cosine scheduler.
- Warmup for 20 epochs.
- Early stopping at 50 epochs.
- Mixed precision training.

However, those YAML settings are not fully reflected in the current `training/train.py`. Therefore, the script should be treated as the executable truth, while the YAML is a design/configuration reference that needs alignment.

## 8. Target Generation

`generate_target_heatmaps_and_offsets()` constructs supervision targets:

1. Landmark coordinates are scaled from image space to heatmap space.
2. A discrete rounded heatmap coordinate is selected.
3. A Gaussian target is drawn around that coordinate.
4. Offset targets are calculated as:

```text
offset_x = continuous_heatmap_x - rounded_heatmap_x
offset_y = continuous_heatmap_y - rounded_heatmap_y
```

5. Offset loss is applied only at peak locations using `peak_masks`.

The code uses anisotropic Gaussian targets:

- Even-indexed landmarks use wider sigma in y.
- Odd-indexed landmarks use wider sigma in x.

This design acknowledges that some anatomical landmarks are naturally more uncertain in one direction than another.

## 9. Loss Functions

Training combines two losses:

### 9.1 Adaptive Wing Loss

The heatmap loss is `AdaptiveWingLoss`, with:

- `omega = 14.0`
- `theta = 0.5`
- `epsilon = 1.0`
- `alpha = 2.1`

Adaptive Wing Loss is suitable for heatmap regression because it emphasizes landmark peak regions and handles small localization errors better than plain mean squared error in many keypoint tasks.

### 9.2 Offset L1 Loss

The offset loss is an L1 loss computed only where `peak_masks == 1`.

This is a good choice because offset values are meaningful only near the actual landmark peak. Applying offset loss across the entire heatmap would force many irrelevant pixels toward zero and dilute useful gradients.

### 9.3 Joint Loss

The final loss is:

```text
total_loss = 1.0 * heatmap_loss + 0.1 * offset_loss
```

This prioritizes correct landmark localization while still rewarding sub-pixel refinement.

## 10. Inference Pipeline

The `/predict` endpoint in `api/main.py` performs:

1. Validate that the HRNet model was loaded at startup.
2. Read uploaded image bytes.
3. Preprocess to a normalized 768 x 768 tensor.
4. Run HRNet inference.
5. Decode heatmaps into landmark coordinates.
6. Apply offsets if available.
7. Map coordinates back to the original image size.
8. Run anatomical shape validation.
9. Build a cephalometric analysis report.

The newer `/ai/detect-landmarks` endpoint performs the same core detection but accepts base64 image input and returns landmarks keyed by clinical short names such as `S`, `N`, `A`, and `B`.

## 11. Post-Processing and Validation

### 11.1 Heatmap Decoding

`postprocess_landmarks()` scales heatmap coordinates back to original image dimensions:

```text
scale_x = original_width / heatmap_width
scale_y = original_height / heatmap_height
```

The output landmark object contains:

- `id`
- `x`
- `y`
- `score`

### 11.2 Optional Intensity-Based Refinement

`refine_landmarks()` can refine points locally using either:

- Intensity peak search.
- Edge-weighted peak search.

This is separate from the neural offset head. Neural offsets refine the heatmap coordinate in model feature space; intensity refinement searches the original image around the predicted point.

### 11.3 Anatomical Shape Validation

`validate_anatomical_shape_constraints()` expects exactly 19 landmarks and computes a Mahalanobis-style anatomical shape distance using `api/anatomical_norms.py`. This helps flag implausible landmark configurations even if individual heatmap peaks appear confident.

There is also `shared/quality.py`, but its `validate_landmarks()` function expects symbolic IDs such as `"S"` and `"N"` while the main pipeline uses integer IDs. That mismatch limits its direct usefulness unless adapted.

## 12. Clinical Measurements Computed

The geometric measurement layer is deterministic. Once landmarks exist, the system calculates angles, distances, and ratios in `api/analysis.py`.

| Measurement | Required landmarks | Meaning |
|---|---|---|
| SNA | S, N, A | Maxillary position relative to cranial base |
| SNB | S, N, B | Mandibular position relative to cranial base |
| ANB | SNA - SNB | Sagittal skeletal jaw relationship |
| Facial Angle (N-S-Gn) | S, N, Gn | Approximate facial growth direction |
| FMA (FH-MP) | Po, Or, Go, Me | Frankfort horizontal vs mandibular plane |
| SN-GoGn | S, N, Go, Gn | Vertical skeletal divergence |
| IMPA | B, LIT, Go, Me | Lower incisor inclination to mandibular plane |
| FMIA | Derived from FMA and IMPA | Tweed triangle component |
| Interincisal angle | B, LIT, UIT | Relationship of upper and lower incisor axes |
| Lower anterior facial height | ANS, Me | Vertical lower-face distance |
| Nasolabial angle | UL, LL, Sn | Soft-tissue profile indicator |
| Articular angle | S, Ar, Go | Jarabak craniofacial growth relation |
| Gonial angle | Ar, Go, Me | Mandibular angle |
| S-Go / N-Me ratio | S, Go, N, Me | Posterior/anterior facial height balance |
| Sum of Jarabak angles | N, S, Ar, Go, Me | Growth-pattern composite |

The measurement layer is not learned. Its accuracy depends on landmark accuracy and pixel calibration.

## 13. Protocols Used

`api/protocols.py` defines the supported analysis protocols:

| Protocol | Measurements included |
|---|---|
| `core_lateral` | SNA, SNB, ANB, FMA, Facial Angle |
| `steiner` | SNA, SNB, ANB, SN-GoGn, FMA, IMPA, FMIA, Interincisal angle |
| `eastman_basic` | SNA, SNB, ANB |
| `eastman` | SNA, SNB, ANB, FMA, SN-GoGn, Interincisal angle |
| `abo_american` | SNA, SNB, ANB, SN-GoGn, FMA, Interincisal angle |
| `tweed` | FMA, IMPA, FMIA |
| `downs` | FMA, Interincisal angle |
| `mcnamara` | Lower anterior facial height, Nasolabial angle |
| `jarabak` | Articular angle, Gonial angle, S-Go/N-Me ratio, angle sum |
| `vertical_basic` | FMA, Facial Angle |

This protocol design is a strong feature because it prevents the system from pretending that every analysis is available from every landmark subset.

## 14. Norms and Classification

Normative comparison is handled in `api/norms.py` and `api/analysis.py`.

For each measurement, the system retrieves:

- Norm mean.
- Norm standard deviation.
- Clinical range/description where available.
- Source metadata.
- Protocol reference.

The classification logic computes:

```text
difference = measured_value - norm_mean
```

Then:

- `normal` if `abs(difference) <= sd`
- `high` if `difference > sd`
- `low` if `difference < -sd`

Interpretation is measurement-specific. For example:

- High SNA -> maxillary prognathism.
- Low SNA -> maxillary retrognathism.
- High SNB -> mandibular prognathism.
- Low SNB -> mandibular retrognathism.
- High ANB -> skeletal Class II tendency.
- Low ANB -> skeletal Class III tendency.
- High FMA/SN-GoGn -> hyperdivergent pattern.
- Low FMA/SN-GoGn -> hypodivergent pattern.
- High IMPA -> proclined lower incisors.
- Low IMPA -> retroclined lower incisors.

## 15. Differences Between the Main Cephalometric Correlations

The repository uses the word "correlation" in a clinical relationship sense more than in a formal statistical sense. The important correlations are relationships between landmarks, angles, measurements, norms, and diagnoses.

### 15.1 Landmark-to-Measurement Correlation

This is the direct geometric dependency between a measurement and its landmarks.

Examples:

- SNA depends on S, N, and A.
- SNB depends on S, N, and B.
- FMA depends on the Frankfort plane points Po/Or and mandibular plane points Go/Me.

This correlation is mechanical: if a required landmark shifts, the measurement changes.

### 15.2 Sagittal Skeletal Correlation

Sagittal correlation describes the anteroposterior relationship between maxilla and mandible.

Key measurements:

- SNA: maxillary position.
- SNB: mandibular position.
- ANB: maxilla-mandible difference.

Clinical interpretation:

- Normal ANB usually supports Class I.
- Increased ANB supports Class II.
- Low or negative ANB supports Class III.

Important distinction:

- ANB identifies the relationship between jaws.
- SNA and SNB help identify the source of the discrepancy.

For example, high ANB may be caused by maxillary protrusion, mandibular retrusion, or both. The diagnostic engine reflects this by using ANB for skeletal class and SNA/SNB for craniofacial pattern details.

### 15.3 Vertical Skeletal Correlation

Vertical correlation describes facial divergence and growth direction.

Key measurements:

- FMA (FH-MP)
- SN-GoGn
- S-Go / N-Me ratio
- Facial Angle (N-S-Gn)

Clinical interpretation:

- Increased FMA or SN-GoGn suggests hyperdivergence.
- Decreased FMA or SN-GoGn suggests hypodivergence.
- A decreased posterior/anterior face-height ratio may support vertical growth tendency.

Difference from sagittal correlation:

- Sagittal correlation classifies jaw relationship front-to-back.
- Vertical correlation classifies facial height, mandibular plane divergence, and growth direction.

### 15.4 Dental Compensation Correlation

Dental correlation evaluates how incisors compensate for skeletal bases.

Key measurements:

- IMPA
- FMIA
- Interincisal angle

Clinical interpretation:

- Increased IMPA suggests proclined lower incisors.
- Decreased IMPA suggests retroclined lower incisors.
- Low interincisal angle may suggest incisor proclination/compensation.

Difference from skeletal correlation:

- Skeletal correlations describe jaw bases.
- Dental correlations describe tooth inclination and compensation.

This matters clinically because a skeletal Class III patient may show dental camouflage, such as retroclined lower incisors or proclined upper incisors. The system's current 19 landmarks support some, but not all, incisor-related measures.

### 15.5 Soft-Tissue Correlation

Soft-tissue correlation links skeletal and dental findings to facial profile.

Key supported measurement:

- Nasolabial angle.

Soft-tissue landmarks:

- Upper Lip
- Lower Lip
- Subnasale
- Soft Tissue Pogonion

Difference from hard-tissue correlations:

- Hard-tissue measurements use skeletal and dental points.
- Soft-tissue measurements describe external profile and esthetic implications.

### 15.6 Protocol-to-Norm Correlation

Different protocols interpret similar measurements under different normative systems. For example:

- Steiner emphasizes SNA, SNB, ANB, SN-GoGn, and incisor measures.
- Tweed emphasizes FMA, IMPA, and FMIA.
- Jarabak emphasizes angular sums and facial height ratios.
- McNamara emphasizes facial height and soft-tissue/linear relationships in the currently supported subset.

This means the same landmark prediction can produce different clinical emphasis depending on selected protocol. The code handles this by mapping `protocol_id` to protocol-specific measurement lists and norm references.

### 15.7 Measurement-Uncertainty Correlation

`api/measurements.py` estimates how landmark uncertainty propagates into measurement uncertainty using Monte-Carlo perturbation.

The system perturbs landmarks with Gaussian noise. The noise scale is influenced by landmark confidence:

```text
sigma = base_sigma_px * (1 - score)
```

Some landmarks use anisotropic perturbation because they are harder to localize in one direction:

- Menton: tighter x, looser y.
- Gonion: looser x, tighter y.
- Gnathion: generally harder.

This relationship is different from clinical correlation. It is an error-propagation correlation: uncertain landmarks lead to uncertain measurements.

### 15.8 Statistical Outlier Correlation

`api/measurement_analysis.py` detects measurements that are far from normative expectations using an IQR-inspired approximation from mean and standard deviation:

```text
lower_bound = mean - 2.698 * sd
upper_bound = mean + 2.698 * sd
```

If a measurement falls outside those bounds, it is flagged as a statistical outlier.

This is not the same as a diagnosis. An outlier may represent true severe anatomy or a landmark error. The code correctly recommends landmark review when outliers appear.

### 15.9 Internal Relationship Correlation

The project also checks whether related measurements are mutually plausible. Examples:

- SNA and SNB should usually be relatively close.
- Positive ANB should not contradict the relative positions implied by SNA/SNB.
- IMPA and FMIA have an expected relationship.
- FMA and SN-GoGn both reflect vertical dimension.

These checks are quality-control correlations. They are intended to catch inconsistent landmark placements or unstable measurements.

## 16. Diagnostic Model / Rule Engine

`api/diagnostic_engine.py` is not a neural network. It is a deterministic clinical rule engine built on top of the measurement report.

It generates:

- Skeletal class.
- Vertical pattern.
- Severity.
- Diagnostic code.
- Craniofacial patterns.
- ICD-10 suggestions.
- Key findings.
- Protocol snapshots.
- Dental pattern.
- Confidence estimate.
- Professional summary.
- Recommendations.

### 16.1 Skeletal Class Rules

The engine prioritizes ANB:

- ANB >= 4.5 -> Class II.
- ANB <= 1.0 -> Class III.
- Otherwise -> Class I.

If ANB is missing, it falls back to SNA/SNB differences.

### 16.2 Vertical Pattern Rules

The vertical pattern uses:

- S-Go / N-Me ratio when available.
- FMA and SN-GoGn differences when available.

Output categories:

- Hyperdivergent.
- Hypodivergent.
- Normodivergent.

### 16.3 Severity Rules

Severity is based on the number and magnitude of abnormal measurements:

- Severe: high maximum z-score or many abnormal rows.
- Moderate: intermediate deviation or multiple abnormal rows.
- Mild: limited deviation.

### 16.4 Confidence Rules

Diagnostic confidence is based on evidence coverage, missing measurements, outlier count, and whether the selected protocol is ready. It is not a calibrated probability from the neural model.

## 17. Treatment Suggestion Engine

`api/treatment_engine.py` converts diagnostic patterns into treatment suggestions. It uses:

- Skeletal class.
- Vertical pattern.
- Dental pattern.
- Severity.
- Age/growth status.

Examples:

- Growing Class II cases may receive functional appliance suggestions.
- Adult moderate/severe skeletal discrepancies may trigger surgical consultation suggestions.
- Hyperdivergent cases trigger vertical-control warnings.
- Proclined lower incisors influence extraction/anchorage considerations.

This is also rule-based. It should be presented as clinical decision support, not autonomous treatment prescription.

## 18. Strengths

1. HRNet is a strong architectural choice for cephalometric landmark localization because it preserves high-resolution spatial representations.
2. Heatmap prediction is more suitable than direct coordinate regression for medical landmark detection.
3. Optional offset regression improves sub-pixel precision.
4. Temperature calibration indicates attention to confidence behavior.
5. The model is integrated into a complete clinical pipeline rather than stopping at landmark coordinates.
6. Protocol validation prevents unsupported measurements from being silently reported.
7. Monte-Carlo uncertainty estimation is a valuable addition for clinical reliability.
8. Measurement outlier detection and anatomical shape validation add useful safety checks.
9. The API is modular, with separate endpoints for detection, measurement, diagnosis, treatment, overlays, and reports.

## 19. Limitations and Risks

1. The production system depends on a single checkpoint: `models/best_model.pth`.
2. Production and training model classes differ, which can cause checkpoint compatibility issues.
3. `strict=False` during checkpoint loading can hide missing or unexpected parameters.
4. The executable training script and `models/config.yaml` are not fully aligned.
5. `models/config.yaml` contains a duplicated `LOSS` section, so the first loss block may be overwritten by YAML parsers.
6. The dataset loader sorts landmarks by symbol rather than using an explicit canonical ID mapping; this could be risky if annotation symbol formats vary.
7. The training dataset may return a variable number of keypoints, while the target generator assumes 19 landmarks.
8. No validation loop or test-set metrics are implemented in `training/train.py`.
9. The current training script saves the best model by training loss only, not validation MRE/SDR.
10. Some clinical API responses use simplified placeholder values, such as default overjet/overbite in `/ai/classify-diagnosis`.
11. Confidence values from the heatmap, diagnostic engine, and treatment engine have different meanings and should not be interpreted as one unified probability.
12. Landmark validation in `shared/quality.py` appears inconsistent with the integer-ID landmark format used by the main pipeline.

## 20. Detailed Error and Gap Audit

This section lists the most important concrete errors, weak points, and development gaps found in the current implementation.

### 20.1 High-Priority Implementation Errors

| Area | Finding | Why it matters | Recommended fix |
|---|---|---|---|
| Checkpoint/model alignment | The deployed checkpoint is heatmap-only, but some documentation describes offset regression as if it may be active. | The system may be credited with sub-pixel neural refinement that the current weights do not provide. | Document the active checkpoint mode at startup and expose `has_offset_head` in health/model metadata. |
| Checkpoint loading | `model.load_state_dict(..., strict=False)` hides missing keys such as `temperature` and all dual-head keys. | Silent partial loading can mask broken or incompatible checkpoints. | Log and fail on unexpected critical mismatches; allow only explicitly whitelisted missing keys. |
| Training vs production classes | `AdvancedHRNetKeypointDetector` and `HRNetKeypointDetector` are separate wrappers with different heads and pretraining assumptions. | A model can train successfully but deploy differently. | Use one shared model factory for both training and inference. |
| Dataset keypoint count | `generate_target_heatmaps_and_offsets()` assumes 19 landmarks but `CephalometricDataset` can return 0 or variable-length keypoints. | Training may fail or silently train on inconsistent landmark order/count. | Enforce canonical 19-landmark tensors with missing-landmark masks. |
| Landmark ordering | Dataset annotations are sorted by `symbol`, not mapped to the canonical IDs in `shared/landmarks.py`. | Lexicographic sorting may misorder landmarks and corrupt supervision. | Build an explicit symbol-to-ID mapping and validate every sample. |
| Measurement relationship validation | `MEASUREMENT_RELATIONSHIPS` uses `("ANB", "SNA", "SNA_higher_than_SNB_when_positive_ANB")`, but the rule logically needs SNA and SNB. | It can generate incorrect warnings because ANB is compared with SNA instead of comparing SNA and SNB. | Rewrite this rule to check `ANB = SNA - SNB` consistency. |
| Refinement suggestions | `suggest_landmark_refinement()` uses landmark names such as `"A"` and `"N"`, but `lm_map` is keyed by integer IDs. | Suggested landmark confidence lookup may fail and recommendations may not connect to actual landmark records. | Map measurement dependencies to integer landmark IDs. |
| Shared quality validation | `shared/quality.py` expects IDs like `"S"` and `"N"`, while main landmarks use integer IDs. | This validation path is incompatible with the main pipeline. | Normalize IDs before validation or rewrite it to use canonical integer IDs. |
| Temperature calibration | The current checkpoint has no saved `temperature`; production uses the initialized value `1.35`. | Calibration may be assumed but is not checkpoint-derived. | Save/load temperature explicitly and report whether it was calibrated. |
| Placeholder clinical values | `/ai/classify-diagnosis` returns default overjet and overbite values of `2.0` and normal classifications. | These values are not computed from landmarks and may be clinically misleading. | Return `null` or compute real values only when required landmarks exist. |

### 20.2 Model and Training Gaps

1. No validation loop is present in `training/train.py`.
2. No test-set evaluation is performed after training.
3. The checkpoint is selected by training loss, not validation accuracy.
4. No MRE, SDR@2mm, SDR@2.5mm, SDR@3mm, or SDR@4mm metrics are computed in the training pipeline.
5. No per-landmark error table is generated, so difficult landmarks such as Gonion, Menton, Articulare, and soft-tissue points are not separately evaluated.
6. No external validation dataset is used to estimate generalization across scanners, populations, age groups, or image qualities.
7. The executable training script uses 10 epochs, while `models/config.yaml` describes 400 epochs, warmup, cosine scheduling, gradient accumulation, and AMP.
8. The YAML file has a duplicated `LOSS` block, so its intended loss configuration is ambiguous.
9. The heatmap score is treated as confidence, but raw heatmap maxima are not calibrated probabilities.
10. The current checkpoint does not use the code's dual-head offset capability.

### 20.3 Clinical and Diagnostic Gaps

1. The diagnostic engine is rule-based, not a trained diagnostic classifier. This is acceptable, but the UI and reports should say so clearly.
2. ANB thresholds in `diagnostic_engine.py` classify `ANB <= 1.0` as Class III. This may overcall borderline cases that are clinically closer to Class I depending on norm/profile context.
3. Wits appraisal is referenced in protocol materials but is not computable from the current 19-landmark set unless occlusal-plane landmarks are added.
4. Upper incisor inclination and upper/lower incisor linear measurements are partially referenced in norms, but not fully computable from the current landmarks.
5. Overjet and overbite are returned by one endpoint as fixed placeholders rather than measured quantities.
6. Growth-stage logic is mainly age/CVM-rule based and should not be presented as image-derived maturity unless cervical vertebral landmarks are explicitly detected or supplied.
7. ICD-10 suggestions are generated from simplified rules and should be treated as coding support, not definitive coding.
8. Treatment suggestions are deterministic rules and should require clinician confirmation.

### 20.4 Reliability and Safety Gaps

1. The API does not expose model version, checkpoint hash, active architecture, landmark count, or offset-head status.
2. There is no minimum landmark confidence gate before downstream diagnosis.
3. There is no automatic rejection path for severe anatomical shape outliers.
4. The system mixes several confidence concepts: heatmap peak score, Monte-Carlo measurement uncertainty, diagnostic evidence coverage, and treatment confidence.
5. These confidence values are not calibrated onto a shared probability scale.
6. Missing landmarks are handled at the protocol layer, but diagnosis endpoints can still create simplified outputs from partial measurement dictionaries.
7. The current tests cover many API behaviors but do not validate true model accuracy, checkpoint compatibility, or clinical measurement correctness against a known cephalometric benchmark.

### 20.5 Documentation Gaps

1. The documentation should clearly state that the active checkpoint is heatmap-only.
2. The difference between supported architecture features and active deployed features should be explicit.
3. Training instructions should specify expected dataset folder structure, annotation schema, landmark symbol mapping, and how missing points are handled.
4. The report should distinguish "AI landmark detection" from "rule-based clinical interpretation."
5. Norm sources should be cited and versioned.
6. Known limitations, especially placeholder values and unsupported measurements, should be visible in UI/exported reports.

### 20.6 Development Roadmap

Recommended development sequence:

1. Stabilize data integrity:
   - canonical landmark ID mapping,
   - fixed 19-point tensors,
   - missing-landmark masks,
   - dataset validation script.
2. Unify model construction:
   - one model factory,
   - explicit architecture metadata,
   - strict checkpoint compatibility checks.
3. Add evaluation:
   - validation split,
   - MRE,
   - SDR thresholds,
   - per-landmark error,
   - per-protocol measurement error.
4. Activate and validate dual-head offsets:
   - train a real offset-head checkpoint,
   - compare heatmap-only vs heatmap+offset performance,
   - report improvement by landmark.
5. Calibrate confidence:
   - temperature calibration on validation data,
   - reliability curves,
   - expected calibration error,
   - clinically meaningful confidence bands.
6. Improve clinical completeness:
   - remove placeholder overjet/overbite,
   - add required landmarks for Wits and occlusal-plane analysis if needed,
   - improve upper-incisor and soft-tissue measurement support.
7. Strengthen safety:
   - block diagnosis on low-quality landmark sets,
   - flag anatomical outliers prominently,
   - require clinician review for severe or uncertain outputs.
8. Improve reproducibility:
   - checkpoint hash,
   - model card,
   - training run metadata,
   - dataset version,
   - norm/reference version.

## 21. Model Comparison

| Model / Approach | Role in this project | Strengths | Limitations |
|---|---|---|---|
| HRNet-W32 | Main production detector | Good balance of resolution, accuracy, and compute | Less capacity than W48 |
| HRNet-W48 | Supported in training wrapper | More channels and representational capacity | Heavier, slower, higher memory use |
| HRNet-W18 | Supported in training wrapper | Faster and lighter | Likely lower accuracy for subtle landmarks |
| Heatmap-only HRNet | Supported by production wrapper | Simple and compatible with older checkpoints | Limited to heatmap-grid precision |
| Dual-head HRNet | Training design and optional production mode | Heatmap localization plus sub-pixel offsets | Requires compatible checkpoint and target generation |
| Direct coordinate regression | Not used | Simple output | Usually weaker for precise anatomical localization |
| U-Net-style encoder-decoder | Not used | Common in medical imaging | May lose fine spatial detail unless carefully designed |
| Rule-based diagnostic engine | Used after measurements | Transparent, explainable, easy to audit | Not a learned diagnostic classifier |

## 22. Recommended Improvements

1. Unify the production and training model classes or provide a formal checkpoint conversion script.
2. Replace `strict=False` with explicit reporting of missing and unexpected keys.
3. Align `models/config.yaml` with the executable training script.
4. Remove the duplicated `LOSS` block in the YAML file.
5. Add validation metrics:
   - Mean Radial Error (MRE).
   - SDR at 2.0 mm, 2.5 mm, 3.0 mm, and 4.0 mm.
   - Per-landmark error.
6. Save checkpoints using validation metrics rather than training loss alone.
7. Enforce canonical landmark ordering by ID/symbol mapping in the dataset loader.
8. Add tests for checkpoint loading in both heatmap-only and dual-head modes.
9. Clearly label diagnostic and treatment outputs as rule-based decision support.
10. Calibrate and document the meaning of `score`, diagnostic confidence, and treatment confidence separately.

## 23. Final Assessment

The project is technically sound as a cephalometric landmark detection and analysis platform. The main neural model, HRNet-W32, is well matched to the task because it preserves high-resolution spatial information and supports heatmap-based localization. The optional offset head further improves precision by reducing the limitation of discrete heatmap coordinates.

The strongest architectural feature is the separation between landmark detection, measurement computation, clinical norms, diagnosis, and treatment reasoning. This makes the system more interpretable and easier to audit than a black-box end-to-end diagnostic model.

The main weaknesses are engineering and validation related: mismatch between training and production wrappers, loose checkpoint loading, incomplete validation metrics in the training script, duplicated configuration sections, and some simplified rule-based outputs that should be clearly documented as decision support.

Overall, the model is a strong foundation for clinical-assistive cephalometric analysis, provided that future work focuses on checkpoint governance, validation metrics, dataset consistency, and transparent separation between neural predictions and rule-based clinical interpretation.
