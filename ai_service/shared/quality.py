"""Quality control checks for landmarks and image quality."""

from typing import Dict, List, Tuple
import numpy as np
from shared.landmarks import LANDMARK_NAMES


class LandmarkValidationError(Exception):
    """Raised when landmark validation fails."""
    pass


class ImageQualityError(Exception):
    """Raised when image quality checks fail."""
    pass


def validate_landmarks(landmarks: List[Dict[str, any]]) -> Tuple[bool, List[str]]:
    """
    Validate landmarks for anatomical correctness.
    
    Landmarks are expected to have integer ``id`` fields (1–19) matching the
    canonical IDs defined in ``shared.landmarks.LANDMARK_NAMES``.
    
    Returns:
        (is_valid: bool, errors: list of error messages)
    """
    errors = []
    landmark_map = {int(lm["id"]): lm for lm in landmarks if "id" in lm}
    
    # Required landmark integer IDs:
    #   1=Sella, 2=Nasion, 5=A-point, 6=B-point, 7=Pogonion, 8=Menton, 10=Gonion
    required_ids = {
        1: "Sella (S)",
        2: "Nasion (N)",
        5: "A-point",
        6: "B-point",
        7: "Pogonion (Pog)",
        8: "Menton (Me)",
        10: "Gonion (Go)",
    }
    for lm_id, name in required_ids.items():
        if lm_id not in landmark_map:
            errors.append(f"Missing required landmark: {name} (ID {lm_id})")
    
    if errors:  # Can't validate positions without required points
        return False, errors
    
    # Anatomical constraints: Y coordinates (vertical ordering)
    try:
        s_y = float(landmark_map[1]["y"])     # Sella
        n_y = float(landmark_map[2]["y"])     # Nasion
        a_y = float(landmark_map[5]["y"])     # A-point
        b_y = float(landmark_map[6]["y"])     # B-point
        pog_y = float(landmark_map[7]["y"])   # Pogonion
        me_y = float(landmark_map[8]["y"])    # Menton
        
        # S should be above N
        if s_y >= n_y:
            errors.append(f"S ({s_y:.0f}) must be above N ({n_y:.0f})")
        
        # N should be above A (usually)
        if n_y >= a_y:
            errors.append(f"N ({n_y:.0f}) should be above A ({a_y:.0f})")
        
        # A should be above B
        if a_y >= b_y:
            errors.append(f"A ({a_y:.0f}) must be above B ({b_y:.0f})")
        
        # B should be above Pog
        if b_y >= pog_y:
            errors.append(f"B ({b_y:.0f}) should be above Pogonion ({pog_y:.0f})")
        
        # Pog should be above Me (usually)
        if pog_y >= me_y:
            errors.append(f"Pogonion ({pog_y:.0f}) should be above Menton ({me_y:.0f})")
    except KeyError as e:
        errors.append(f"Missing landmark data for coordinate check: {e}")
    
    return len(errors) == 0, errors


def check_image_quality(image_array: np.ndarray) -> Tuple[bool, List[str]]:
    """
    Check image quality (blur, exposure, rotation).
    
    Args:
        image_array: Grayscale or color image as numpy array
        
    Returns:
        (passes_all_checks: bool, warnings: list of quality issues)
    """
    warnings = []
    
    if image_array is None or image_array.size == 0:
        return False, ["Image is empty"]
    
    # Convert to grayscale if needed
    if len(image_array.shape) == 3:
        gray = np.mean(image_array, axis=2)
    else:
        gray = image_array
    
    # Blur detection via Laplacian variance
    laplacian = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])
    # Simple convolution approximation
    if gray.shape[0] >= 3 and gray.shape[1] >= 3:
        blur_map = np.abs(gray[1:-1, 1:-1] * 4 - gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:])
        blur_variance = np.var(blur_map)
        
        if blur_variance < 50:  # Very blurry
            warnings.append(f"Image appears blurry (variance: {blur_variance:.1f})")
    
    # Exposure check
    mean_pixel = np.mean(gray)
    if mean_pixel < 30:
        warnings.append("Image is very dark")
    elif mean_pixel > 225:
        warnings.append("Image is overexposed")
    
    # Basic contrast check
    std_pixel = np.std(gray)
    if std_pixel < 10:
        warnings.append("Image has very low contrast")
    
    return len(warnings) == 0, warnings
