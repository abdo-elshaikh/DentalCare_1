import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional


def find_periodic_peaks(signal: np.ndarray, min_dist: int = 5, prominence: float = 0.15) -> np.ndarray:
    """
    Robust peak finder for 1D signal.
    Finds local maxima that are significantly higher than their surroundings.
    """
    if len(signal) == 0:
        return np.array([])
    
    # Normalize signal to [0, 1]
    s_min, s_max = signal.min(), signal.max()
    if s_max - s_min == 0:
        return np.array([])
    norm_s = (signal - s_min) / (s_max - s_min)
    
    peaks = []
    for i in range(1, len(norm_s) - 1):
        if norm_s[i] > norm_s[i - 1] and norm_s[i] > norm_s[i + 1]:
            # Check prominence / height local constraint
            local_window = norm_s[max(0, i - min_dist):min(len(norm_s), i + min_dist + 1)]
            if norm_s[i] >= np.mean(local_window) + prominence:
                peaks.append(i)
                
    # Filter double peaks within min_dist
    filtered_peaks = []
    for p in peaks:
        if not filtered_peaks or p - filtered_peaks[-1] >= min_dist:
            filtered_peaks.append(p)
            
    return np.array(filtered_peaks)


def auto_detect_px_to_mm(image_bytes: bytes, tick_interval_mm: float = 10.0) -> Dict[str, Any]:
    """
    CV-based Automatic Scale Calibration for lateral cephalograms.
    Detects periodic lead ruler grids/ticks along the frame boundaries
    and calculates pixel distance for the specified tick_interval_mm (default 10mm).
    
    Returns:
        Dict containing:
            "success": bool
            "px_to_mm": float (if successful, else 1.0)
            "pixel_distance": float (average pixels per tick_interval_mm)
            "real_distance_mm": float
            "ruler_orientation": str ("vertical", "horizontal", or "none")
            "message": str
    """
    # 1. Decode image
    img_np = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {
            "success": False,
            "px_to_mm": 1.0,
            "pixel_distance": 0.0,
            "real_distance_mm": tick_interval_mm,
            "ruler_orientation": "none",
            "message": "Failed to decode image bytes."
        }
        
    h, w = img.shape
    
    # 2. Define search zones (crop borders where rulers typically reside)
    # - Zone A: Left border strip (common for vertical rulers)
    # - Zone B: Top border strip (common for horizontal rulers)
    left_strip = img[:, :int(w * 0.12)]
    top_strip = img[:int(h * 0.12), :]
    
    # 3. Analyze Left Strip (Vertical Ruler detection)
    # Apply adaptive thresholding to enhance high-contrast tick marks
    left_thresh = cv2.adaptiveThreshold(
        left_strip, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 21, 5
    )
    
    # Row-wise projection profile (sum horizontally to find periodic horizontal lines/ticks)
    # Ticks are usually dark on light or light on dark; adaptive thresholding handles both.
    row_sum = np.sum(255 - left_thresh, axis=1)
    
    # Smooth signal to filter pixel-level noise
    row_sum_smoothed = cv2.GaussianBlur(row_sum.astype(np.float32), (1, 9), 0).flatten()
    
    # Find periodic peaks
    # Let's assume tick spacing is at least 15 pixels and at most 250 pixels
    peaks_v = find_periodic_peaks(row_sum_smoothed, min_dist=15, prominence=0.2)
    
    if len(peaks_v) >= 3:
        # Calculate spacing between adjacent peaks
        spacings = np.diff(peaks_v)
        # Use median to resist outlier noise/spurs
        median_spacing = float(np.median(spacings))
        
        # Simple sanity check: spacing shouldn't be too small or too large
        # If it is plausible, return scale
        if 20.0 <= median_spacing <= 350.0:
            px_to_mm = tick_interval_mm / median_spacing
            return {
                "success": True,
                "px_to_mm": round(px_to_mm, 8),
                "pixel_distance": round(median_spacing, 4),
                "real_distance_mm": float(tick_interval_mm),
                "ruler_orientation": "vertical",
                "message": f"Successfully detected vertical ruler with periodic tick spacing of {median_spacing:.2f} pixels."
            }
            
    # 4. Analyze Top Strip (Horizontal Ruler detection)
    top_thresh = cv2.adaptiveThreshold(
        top_strip, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 21, 5
    )
    
    # Column-wise projection profile
    col_sum = np.sum(255 - top_thresh, axis=0)
    col_sum_smoothed = cv2.GaussianBlur(col_sum.astype(np.float32), (9, 1), 0).flatten()
    
    peaks_h = find_periodic_peaks(col_sum_smoothed, min_dist=15, prominence=0.2)
    
    if len(peaks_h) >= 3:
        spacings = np.diff(peaks_h)
        median_spacing = float(np.median(spacings))
        
        if 20.0 <= median_spacing <= 350.0:
            px_to_mm = tick_interval_mm / median_spacing
            return {
                "success": True,
                "px_to_mm": round(px_to_mm, 8),
                "pixel_distance": round(median_spacing, 4),
                "real_distance_mm": float(tick_interval_mm),
                "ruler_orientation": "horizontal",
                "message": f"Successfully detected horizontal ruler with periodic tick spacing of {median_spacing:.2f} pixels."
            }
            
    # 5. Fail gracefully
    return {
        "success": False,
        "px_to_mm": 1.0,
        "pixel_distance": 0.0,
        "real_distance_mm": tick_interval_mm,
        "ruler_orientation": "none",
        "message": "Could not automatically detect a periodic calibration ruler in standard border areas. Please use manual ruler calibration."
    }
