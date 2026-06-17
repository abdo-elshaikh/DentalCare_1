import os
import json
import numpy as np
import cv2
import torch
from torch.utils.data import Dataset
import albumentations as A
from albumentations.pytorch import ToTensorV2

SYMBOL_TO_INDEX: dict[str, int] = {
    "S": 0,       # 1. Sella
    "N": 1,       # 2. Nasion
    "Or": 2,      # 3. Orbitale
    "Po": 3,      # 4. Porion
    "A": 4,       # 5. A-point (Subspinale)
    "B": 5,       # 6. B-point (Supramentale)
    "Pog": 6,     # 7. Pogonion
    "Me": 7,      # 8. Menton
    "Gn": 8,      # 9. Gnathion
    "Go": 9,      # 10. Gonion
    "LIT": 10,    # 11. Lower Incisor Tip
    "UIT": 11,    # 12. Upper Incisor Tip
    "UL": 12,     # 13. Upper Lip  (Labrale superius / Ls)
    "LL": 13,     # 14. Lower Lip  (Labrale inferius / Li)
    "Sn": 14,     # 15. Subnasale
    "Pog'": 15,   # 16. Soft Tissue Pogonion
    "PNS": 16,    # 17. Posterior Nasal Spine
    "ANS": 17,    # 18. Anterior Nasal Spine
    "Ar": 18,     # 19. Articulare
}

SYMBOL_ALIASES: dict[str, str] = {
    "Ls": "UL",
    "Li": "LL",
    "Pog`": "Pog'",
    "PNS'": "PNS",
    "ANS'": "ANS",
}

NUM_LANDMARKS = 19


class CephalometricDataset(Dataset):
    def __init__(self, data_dir, split="train", img_size=(768, 768), augment=False):
        """
        data_dir: Path to `dataset/`
        split: 'train', 'valid', or 'test'
        img_size: Target image size (height, width)
        augment: Whether to apply data augmentations
        """
        self.data_dir = data_dir
        self.split = split
        self.img_size = img_size
        self.augment = augment
        
        self.image_dir = os.path.join(data_dir, split, "Cephalograms")
        self.annot_dir = os.path.join(data_dir, split, "Annotations", "Cephalometric Landmarks")
        
        # Gather all image files
        self.image_files = []
        if os.path.exists(self.image_dir):
            for f in os.listdir(self.image_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    self.image_files.append(f)
                    
        self.transform = self._get_transforms()

    def _get_transforms(self):
        transforms_list = []
        
        if self.augment:
            transforms_list.extend([
                # Photometric
                A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=0.5),
                A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
                A.RandomGamma(gamma_limit=(80, 120), p=0.3),
                
                # Geometric - NO horizontal flips for lateral cephs!
                A.ShiftScaleRotate(
                    shift_limit=0.05, 
                    scale_limit=0.15, 
                    rotate_limit=15, 
                    border_mode=cv2.BORDER_CONSTANT, 
                    p=0.8
                ),
                
                # Coarse Dropout (Cutout)
                A.CoarseDropout(
                    num_holes_range=(1, 4), 
                    hole_height_range=(16, 64), 
                    hole_width_range=(16, 64), 
                    fill=0, 
                    p=0.3
                )
            ])
            
        # Base transforms (Resize & ToTensor)
        transforms_list.extend([
            A.Resize(height=self.img_size[0], width=self.img_size[1]),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]), # standard ImageNet normalize
            ToTensorV2()
        ])
        
        return A.Compose(
            transforms_list,
            keypoint_params=A.KeypointParams(format='xy', remove_invisible=False)
        )

    def _load_annotations(self, ceph_id):
        """Finds the JSON annotation for a given ceph_id."""
        for level in ["Senior Orthodontists", "Junior Orthodontists"]:
            json_path = os.path.join(self.annot_dir, level, f"{ceph_id}.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                return data['landmarks']
        return []

    def _map_landmarks_to_canonical(self, landmarks_data):
        """Map annotation landmarks to a fixed-order array of shape (NUM_LANDMARKS, 2).

        Returns:
            keypoints: np.ndarray of shape (NUM_LANDMARKS, 2).
                       Missing landmarks are filled with (-1, -1) which signals
                       to the heatmap generator to skip them.
        """
        keypoints = np.full((NUM_LANDMARKS, 2), -1.0, dtype=np.float32)

        for lm in landmarks_data:
            symbol = lm.get("symbol", "")

            # Resolve aliases (e.g., "Ls" → "UL")
            symbol = SYMBOL_ALIASES.get(symbol, symbol)

            idx = SYMBOL_TO_INDEX.get(symbol)
            if idx is None:
                # This landmark exists in the 29-point annotation but is not
                # part of the 19-landmark model — skip silently.
                continue

            keypoints[idx, 0] = float(lm["value"]["x"])
            keypoints[idx, 1] = float(lm["value"]["y"])

        return keypoints

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_name = self.image_files[idx]
        ceph_id = os.path.splitext(img_name)[0]
        
        # Load Image (with null-check)
        img_path = os.path.join(self.image_dir, img_name)
        image = cv2.imread(img_path)
        if image is None:
            raise IOError(f"Failed to load image: {img_path}")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Load Landmarks — map to canonical 19-point order
        landmarks_data = self._load_annotations(ceph_id)
        keypoints = self._map_landmarks_to_canonical(landmarks_data)

        # Build a list of (x, y) tuples for albumentations (only valid landmarks)
        valid_mask = keypoints[:, 0] >= 0
        kp_list = [tuple(kp) for kp in keypoints[valid_mask]]

        # Apply transforms
        if len(kp_list) > 0:
            transformed = self.transform(image=image, keypoints=kp_list)
            image = transformed['image']
            # Reconstruct the full (NUM_LANDMARKS, 2) array, putting transformed
            # keypoints back into the correct canonical positions.
            transformed_kps = np.array(transformed['keypoints'], dtype=np.float32)
            full_kps = np.full((NUM_LANDMARKS, 2), -1.0, dtype=np.float32)
            j = 0
            for i in range(NUM_LANDMARKS):
                if valid_mask[i]:
                    full_kps[i] = transformed_kps[j]
                    j += 1
            keypoints = full_kps
        else:
            # Fallback if no annotations
            transformed = self.transform(image=image, keypoints=[])
            image = transformed['image']
            keypoints = np.full((NUM_LANDMARKS, 2), -1.0, dtype=np.float32)
            
        # Convert keypoints to torch tensor
        keypoints = torch.tensor(keypoints, dtype=torch.float32)
        
        return image, keypoints, ceph_id
