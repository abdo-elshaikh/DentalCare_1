import torch
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
import cv2

from .dataset import CephalometricDataset
from .model import HRNetKeypointDetector
from .loss import JointCoordinateOffsetLoss

def generate_target_heatmaps_and_offsets(keypoints, image_size, feature_size, num_landmarks=19, sigma=2.0):
    """
    Generates Anisotropic Gaussian heatmaps, corresponding (x, y) offsets, and peak masks.
    keypoints: (N, 19, 2) tensor in original image scale
    image_size: (H, W) of the input image
    feature_size: (H_f, W_f) of the output heatmap
    """
    batch_size = keypoints.shape[0]
    H_f, W_f = feature_size
    H, W = image_size
    
    stride_y = H / H_f
    stride_x = W / W_f
    
    heatmaps = torch.zeros((batch_size, num_landmarks, H_f, W_f), dtype=torch.float32)
    offsets = torch.zeros((batch_size, num_landmarks * 2, H_f, W_f), dtype=torch.float32)
    peak_masks = torch.zeros((batch_size, num_landmarks * 2, H_f, W_f), dtype=torch.float32)
    
    for b in range(batch_size):
        for k in range(num_landmarks):
            kx, ky = keypoints[b, k, 0], keypoints[b, k, 1]
            
            # Ignore missing landmarks or keypoints augmented out of bounds
            if kx <= 0 or ky <= 0 or kx >= W or ky >= H:
                continue
                
            # Map coordinate to feature map scale
            f_x = kx / stride_x
            f_y = ky / stride_y
            
            # Discrete coordinates
            d_x = int(torch.round(f_x))
            d_y = int(torch.round(f_y))
            
            # Offsets (continuous - discrete)
            off_x = f_x - d_x
            off_y = f_y - d_y
            
            # Generate Anisotropic Gaussian
            sigma_x = sigma if k % 2 == 0 else sigma * 1.5
            sigma_y = sigma if k % 2 != 0 else sigma * 1.5
            
            # Bounding box for the gaussian
            radius_x = int(3 * sigma_x)
            radius_y = int(3 * sigma_y)
            
            y_range = torch.arange(-radius_y, radius_y + 1, dtype=torch.float32)
            x_range = torch.arange(-radius_x, radius_x + 1, dtype=torch.float32)
            yy, xx = torch.meshgrid(y_range, x_range, indexing='ij')
            
            gaussian = torch.exp(-(xx**2 / (2 * sigma_x**2) + yy**2 / (2 * sigma_y**2)))
            
            # Sub-region in heatmap
            top = max(0, d_y - radius_y)
            bottom = min(H_f, d_y + radius_y + 1)
            left = max(0, d_x - radius_x)
            right = min(W_f, d_x + radius_x + 1)
            
            # Sub-region in gaussian
            g_top = top - (d_y - radius_y)
            g_bottom = gaussian.shape[0] - ((d_y + radius_y + 1) - bottom)
            g_left = left - (d_x - radius_x)
            g_right = gaussian.shape[1] - ((d_x + radius_x + 1) - right)
            
            if top < bottom and left < right:
                heatmaps[b, k, top:bottom, left:right] = torch.maximum(
                    heatmaps[b, k, top:bottom, left:right],
                    gaussian[g_top:g_bottom, g_left:g_right]
                )
                
                # Assign offsets and peak masks only at the peak location
                if 0 <= d_y < H_f and 0 <= d_x < W_f:
                    offsets[b, k*2, d_y, d_x] = off_x
                    offsets[b, k*2 + 1, d_y, d_x] = off_y
                    peak_masks[b, k*2, d_y, d_x] = 1.0
                    peak_masks[b, k*2 + 1, d_y, d_x] = 1.0

    return heatmaps, offsets, peak_masks

def train_one_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    
    for images, keypoints, ceph_ids in dataloader:
        images = images.to(device)
        
        # We assume output feature map is 1/4 the input resolution for HRNet
        feature_size = (images.shape[2] // 4, images.shape[3] // 4)
        
        # Generate Ground Truth
        true_heatmaps, true_offsets, peak_masks = generate_target_heatmaps_and_offsets(
            keypoints, (images.shape[2], images.shape[3]), feature_size
        )
        
        true_heatmaps = true_heatmaps.to(device)
        true_offsets = true_offsets.to(device)
        peak_masks = peak_masks.to(device)
        
        optimizer.zero_grad()
        
        # Forward pass
        pred_heatmaps, pred_offsets = model(images)
        
        # Compute Loss
        loss = criterion(pred_heatmaps, pred_offsets, true_heatmaps, true_offsets, peak_masks)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        
    return total_loss / len(dataloader)

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training on {device}")
    
    # 1. Setup Data
    train_dataset = CephalometricDataset(data_dir='./dataset', split='train', augment=True)
    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True, num_workers=0)
    
    # 2. Setup Model
    model = HRNetKeypointDetector(num_landmarks=19, backbone='hrnet_w32').to(device)
    
    # 3. Setup Loss and Optimizer
    criterion = JointCoordinateOffsetLoss(lambda_heatmap=1.0, lambda_offset=0.1).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    
    # 4. Training Loop
    epochs = 10
    best_loss = float('inf')
    
    import os
    os.makedirs('../models', exist_ok=True)
    
    for epoch in range(epochs):
        loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        print(f"Epoch {epoch+1}/{epochs} - Loss: {loss:.4f}")
        
        # Save best model
        if loss < best_loss:
            best_loss = loss
            torch.save({'model_state_dict': model.state_dict()}, '../models/best_model.pth')
            print("Saved new best model.")
            
    print("Training complete! Model saved to ../models/best_model.pth")

if __name__ == '__main__':
    main()
