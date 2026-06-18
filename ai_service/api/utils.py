import numpy as np
from PIL import Image
import torch
import cv2
from shared.landmarks import LANDMARK_SHORTS

try:
    from .anatomical_norms import compute_shape_mahalanobis_distance
except ImportError:
    from anatomical_norms import compute_shape_mahalanobis_distance

def preprocess_image(image_bytes, target_size=(768, 768)):
    """
    Resize to target_size, normalize, and convert to tensor.
    """
    # Read image from bytes
    image_np = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid or unsupported image data")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Keep original size for later mapping
    original_size = (image.shape[1], image.shape[0]) # (width, height)
    
    # Resize image
    image = cv2.resize(image, target_size)
    
    # Normalize: using mean and std from config
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    image = (image.astype(np.float32) / 255.0 - mean) / std
    
    # Convert to tensor (Channels, Height, Width)
    image = np.transpose(image, (2, 0, 1))
    tensor = torch.from_numpy(image).unsqueeze(0).float()
    
    return tensor, original_size

def get_max_preds(batch_heatmaps):
    """
    Get predictions from heatmaps.
    Returns: coords (batch_size, num_joints, 2), maxvals (batch_size, num_joints, 1)
    """
    batch_size = batch_heatmaps.shape[0]
    num_joints = batch_heatmaps.shape[1]
    width = batch_heatmaps.shape[3]
    heatmaps_reshaped = batch_heatmaps.reshape((batch_size, num_joints, -1))
    idx = np.argmax(heatmaps_reshaped, 2)
    maxvals = np.amax(heatmaps_reshaped, 2)

    maxvals = maxvals.reshape((batch_size, num_joints, 1))
    idx = idx.reshape((batch_size, num_joints, 1))

    preds = np.tile(idx, (1, 1, 2)).astype(np.float32)

    preds[:, :, 0] = (preds[:, :, 0]) % width
    preds[:, :, 1] = np.floor((preds[:, :, 1]) / width)

    pred_mask = np.tile(np.greater(maxvals, 0.0), (1, 1, 2))
    pred_mask = pred_mask.astype(np.float32)

    preds *= pred_mask
    return preds, maxvals

def postprocess_landmarks(heatmaps, original_size, target_size=(768, 768), offsets=None):
    """
    Map heatmaps (which are output size, typically 1/4 of target_size or same)
    back to original image size.
    For HRNet-W32 branch 0, output is actually target_size / 4 usually, but wait, 
    our wrapper returns features[0] which is target_size / 4 (e.g. 192x192 if input is 768x768).
    We extract coordinates from 192x192 heatmaps and map them to original_size.
    Optional sub-pixel offset refinement can be performed if `offsets` is provided.
    """
    heatmaps_np = heatmaps.cpu().numpy()
    
    # Extract coordinates
    coords, maxvals = get_max_preds(heatmaps_np)
    
    # Coords are currently at the heatmap resolution
    heatmap_h, heatmap_w = heatmaps_np.shape[2], heatmaps_np.shape[3]
    
    # Original width and height
    orig_w, orig_h = original_size
    
    # Scale coordinates back to original image size
    # x scale = orig_w / heatmap_w
    # y scale = orig_h / heatmap_h
    scale_x = orig_w / heatmap_w
    scale_y = orig_h / heatmap_h
    
    if offsets is not None:
        offsets_np = offsets.cpu().numpy()
        
    landmarks = []
    # Loop over the landmarks in the first batch item
    for i in range(coords.shape[1]):
        x = coords[0, i, 0]
        y = coords[0, i, 1]
        
        if offsets is not None:
            # Sub-pixel continuous offsets refinement
            d_x = max(0, min(heatmap_w - 1, int(round(x))))
            d_y = max(0, min(heatmap_h - 1, int(round(y))))
            
            off_x = offsets_np[0, i * 2, d_y, d_x]
            off_y = offsets_np[0, i * 2 + 1, d_y, d_x]
            
            x = x + off_x
            y = y + off_y
            
        x_scaled = x * scale_x
        y_scaled = y * scale_y
        score = float(maxvals[0, i, 0])
        
        landmarks.append({
            "id": i + 1,
            "name": LANDMARK_SHORTS.get(i + 1, "Unknown"),
            "x": round(float(x_scaled), 2),
            "y": round(float(y_scaled), 2),
            "score": round(score, 4)
        })
        
    return landmarks


def refine_landmarks(image_bytes, landmarks, window=21, method='intensity'):
    """
    Refine each landmark to the nearest local intensity maximum within a square window.
    - image_bytes: raw image bytes
    - landmarks: list of dicts with keys 'id','x','y'
    - window: odd integer window size (pixels)
    Returns: list of landmark dicts with updated x,y and score (intensity)
    """
    import cv2

    img_np = np.frombuffer(image_bytes, np.uint8)
    img_color = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
    if img_color is None:
        raise ValueError('Failed to decode image for refinement')

    gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    half = window // 2

    refined = []
    for lm in landmarks:
        x = int(round(lm.get('x', 0)))
        y = int(round(lm.get('y', 0)))

        x0 = max(0, x - half)
        x1 = min(w, x + half + 1)
        y0 = max(0, y - half)
        y1 = min(h, y + half + 1)

        crop = gray[y0:y1, x0:x1]
        if crop.size == 0:
            refined.append({
                'id': lm.get('id'),
                'name': lm.get('name', 'Unknown'),
                'x': float(x),
                'y': float(y),
                'score': 0.0
            })
            continue

        if method == 'intensity':
            crop_blur = cv2.GaussianBlur(crop, (5, 5), 0)
            minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(crop_blur)
            best_x = x0 + maxLoc[0]
            best_y = y0 + maxLoc[1]
            best_score = float(maxVal)
        else:
            # Edge-weighted peak: prefer strong gradient/edge locations
            edges = cv2.Canny(crop, 50, 150)
            gx = cv2.Sobel(crop, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(crop, cv2.CV_64F, 0, 1, ksize=3)
            grad = np.sqrt(gx**2 + gy**2)
            if grad.max() > 0:
                grad = grad / (grad.max() + 1e-12)
            score_map = (edges.astype(np.float32) / 255.0) * grad
            # add small weight from intensity to help isolated peaks
            score_map += (crop.astype(np.float32) / 255.0) * 0.1
            idx = np.unravel_index(np.argmax(score_map), score_map.shape)
            best_y_loc, best_x_loc = idx
            best_x = x0 + int(best_x_loc)
            best_y = y0 + int(best_y_loc)
            best_score = float(score_map[best_y_loc, best_x_loc])

        refined.append({
            'id': lm.get('id'),
            'name': lm.get('name', 'Unknown'),
            'x': round(float(best_x), 2),
            'y': round(float(best_y), 2),
            'score': best_score
        })

    return refined


def validate_anatomical_shape_constraints(landmarks):
    """
    Checks if the coordinates shape of the list of landmarks violates anatomical constraints.
    landmarks: List of dicts, each with keys 'x', 'y' and 'id'.
    Returns:
        Dict containing Mahalanobis stats.
    """
    if len(landmarks) != 19:
        return {
            "mahalanobis_distance": 999.0,
            "is_anatomical_outlier": True,
            "p_value": 0.0,
            "message": f"Expected exactly 19 standard landmarks for anatomical shape validation, got {len(landmarks)}."
        }
    
    # Extract coordinates in ordered form (1 to 19)
    try:
        sorted_lms = sorted(landmarks, key=lambda x: int(x.get('id', 0)))
        coords = np.array([[float(lm['x']), float(lm['y'])] for lm in sorted_lms], dtype=np.float32)
        return compute_shape_mahalanobis_distance(coords)
    except Exception as e:
        return {
            "mahalanobis_distance": 999.0,
            "is_anatomical_outlier": True,
            "p_value": 0.0,
            "message": f"Failed to calculate Mahalanobis distance: {str(e)}."
        }
