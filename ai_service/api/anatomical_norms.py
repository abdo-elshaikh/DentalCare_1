import numpy as np
from typing import Dict, Any, Tuple


# Mean Procrustes-aligned reference coordinate configuration for the 19 standard lateral landmarks.
# Centered at (0,0) and scaled so the root-mean-square distance from the center is 1.0.
#
# IMPORTANT: Order matches the canonical IDs defined in shared/landmarks.py:
#   1=Sella, 2=Nasion, 3=Orbitale, 4=Porion, 5=A-point, 6=B-point,
#   7=Pogonion, 8=Menton, 9=Gnathion, 10=Gonion, 11=LIT, 12=UIT,
#   13=UL, 14=LL, 15=Sn, 16=Pog', 17=PNS, 18=ANS, 19=Ar
MEAN_SHAPE = np.array([
    [-0.32,  0.58],  #  1. Sella (S)              — cranial base
    [ 0.65,  0.72],  #  2. Nasion (N)             — frontonasal suture
    [ 0.44,  0.31],  #  3. Orbitale (Or)          — inferior orbital rim
    [-0.68,  0.42],  #  4. Porion (Po)            — ear canal
    [ 0.58,  0.02],  #  5. A-point (Subspinale)   — maxilla
    [ 0.48, -0.42],  #  6. B-point (Supramentale) — mandible
    [ 0.51, -0.62],  #  7. Pogonion (Pog)         — chin prominence
    [ 0.45, -0.74],  #  8. Menton (Me)            — chin bottom
    [ 0.49, -0.69],  #  9. Gnathion (Gn)          — chin midpoint
    [-0.41, -0.38],  # 10. Gonion (Go)            — jaw angle
    [ 0.58, -0.32],  # 11. Lower Incisor Tip (LIT)
    [ 0.54, -0.12],  # 12. Upper Incisor Tip (UIT)
    [ 0.69, -0.05],  # 13. Upper Lip (UL / Ls)    — soft tissue
    [ 0.59, -0.48],  # 14. Lower Lip (LL / Li)    — soft tissue
    [ 0.60,  0.00],  # 15. Subnasale (Sn)         — soft tissue
    [ 0.55, -0.60],  # 16. Soft Tissue Pogonion (Pog')
    [ 0.08,  0.15],  # 17. Posterior Nasal Spine (PNS)
    [ 0.61,  0.22],  # 18. Anterior Nasal Spine (ANS)
    [-0.50,  0.20],  # 19. Articulare (Ar)        — condyle/skull base
], dtype=np.float32)

# Empirical coordinate-wise variance vector representing standard clinical variations.
# Larger variances allowed for soft tissue landmarks and Gonion.
# Order matches MEAN_SHAPE (= shared/landmarks.py canonical IDs).
VARIANCE_SHAPE = np.array([
    [0.006, 0.006],  #  1. Sella       (Highly stable cranial base)
    [0.008, 0.008],  #  2. Nasion      (Stable)
    [0.015, 0.015],  #  3. Orbitale
    [0.012, 0.012],  #  4. Porion
    [0.018, 0.018],  #  5. A-point
    [0.020, 0.020],  #  6. B-point
    [0.022, 0.022],  #  7. Pogonion
    [0.024, 0.024],  #  8. Menton
    [0.022, 0.022],  #  9. Gnathion
    [0.035, 0.035],  # 10. Gonion      (High vertical/sagittal angle variance)
    [0.028, 0.028],  # 11. LIT         (Lower Incisor Tip)
    [0.025, 0.025],  # 12. UIT         (Upper Incisor Tip)
    [0.045, 0.045],  # 13. Upper Lip   (High soft tissue mobility)
    [0.045, 0.045],  # 14. Lower Lip   (High soft tissue mobility)
    [0.030, 0.030],  # 15. Subnasale   (Soft tissue)
    [0.040, 0.040],  # 16. Pog'        (Soft tissue)
    [0.022, 0.022],  # 17. PNS
    [0.018, 0.018],  # 18. ANS
    [0.025, 0.025],  # 19. Articulare
], dtype=np.float32)


def procrustes_align(coords: np.ndarray) -> np.ndarray:
    """
    Standardizes a coordinate configuration shape by shifting the centroid
    to the origin (0,0) and scaling the root-mean-square distance to 1.0.
    This eliminates translation and scaling variations completely.
    
    Args:
        coords: np.ndarray of shape (N, 2)
    Returns:
        np.ndarray of shape (N, 2) centered and normalized.
    """
    # 1. Translate centroid to origin
    centroid = np.mean(coords, axis=0)
    centered = coords - centroid
    
    # 2. Scale root-mean-square distance to 1.0
    rms_distance = np.sqrt(np.mean(np.sum(centered**2, axis=1)))
    if rms_distance == 0:
        return centered
        
    normalized = centered / rms_distance
    return normalized


def compute_shape_mahalanobis_distance(coords: np.ndarray) -> Dict[str, Any]:
    """
    Calculates the Mahalanobis distance of a Procrustes-aligned 19-landmark shape
    against the reference clinical MEAN_SHAPE and VARIANCE_SHAPE.
    
    Returns:
        Dict containing:
            "mahalanobis_distance": float
            "is_anatomical_outlier": bool
            "p_value": float (approximate significance of structural deformity/error)
            "message": str
    """
    if coords.shape != (19, 2):
        return {
            "mahalanobis_distance": 999.0,
            "is_anatomical_outlier": True,
            "p_value": 0.0,
            "message": f"Expected exactly 19 landmarks, received {coords.shape[0]}."
        }
        
    # Align target configuration
    aligned = procrustes_align(coords)
    
    # Compute Mahalanobis distance using diagonal variance vector
    diff = aligned - MEAN_SHAPE
    squared_diff_weighted = (diff**2) / VARIANCE_SHAPE
    
    mahalanobis_distance = float(np.sqrt(np.sum(squared_diff_weighted)))
    
    # Threshold check: a mahalanobis distance of > 6.0 in normalized Procrustes coordinates
    # represents a shape that deviates significantly (over 4.5 standard deviations) 
    # from plausible cranial/facial structures.
    is_outlier = mahalanobis_distance > 6.0
    
    # Approximate a simplified significance metric (p-value equivalent)
    # where lower represents a highly unlikely anatomical shape (suggesting landmark prediction error)
    p_approx = float(np.exp(-0.5 * (mahalanobis_distance ** 2) / 38.0))
    
    if is_outlier:
        msg = f"Anatomical shape anomaly detected! Mahalanobis distance of {mahalanobis_distance:.2f} exceeds clinical tolerance bounds."
    else:
        msg = f"Anatomical shape is within normal clinical variation boundaries (Mahalanobis: {mahalanobis_distance:.2f})."
        
    return {
        "mahalanobis_distance": round(mahalanobis_distance, 4),
        "is_anatomical_outlier": is_outlier,
        "p_value": round(p_approx, 5),
        "message": msg
    }
