import torch
import torch.nn as nn

class AdaptiveWingLoss(nn.Module):
    def __init__(self, omega=14.0, theta=0.5, epsilon=1.0, alpha=2.1):
        """
        Adaptive Wing Loss for heatmap-based landmark detection.
        Args:
            omega: controls the threshold for switching between linear and non-linear parts
            theta: controls the threshold for switching between linear and non-linear parts
            epsilon: controls the curvature
            alpha: regulates the non-linear part to be close to zero when error is small
        """
        super(AdaptiveWingLoss, self).__init__()
        self.omega = omega
        self.theta = theta
        self.epsilon = epsilon
        self.alpha = alpha

    def forward(self, y_pred, y_true):
        """
        Args:
            y_pred: Predicted heatmaps (N, C, H, W)
            y_true: Ground truth heatmaps (N, C, H, W)
        """
        # Calculate the absolute error
        delta = torch.abs(y_true - y_pred)
        
        # Adaptive adjustment for the true heatmaps (focusing more on the peaks)
        A = self.omega * (1 / (1 + torch.pow(self.theta / self.epsilon, self.alpha - y_true))) * (self.alpha - y_true) * \
            torch.pow(self.theta / self.epsilon, self.alpha - y_true - 1) * (1 / self.epsilon)
            
        C = (self.theta * A) - self.omega * torch.log(1 + torch.pow(self.theta / self.epsilon, self.alpha - y_true))

        # Condition for switching between linear and non-linear loss
        loss1 = self.omega * torch.log(1 + torch.pow(delta / self.epsilon, self.alpha - y_true))
        loss2 = A * delta - C

        # Combine based on threshold theta
        loss = torch.where(delta < self.theta, loss1, loss2)
        
        return torch.mean(loss)

class JointCoordinateOffsetLoss(nn.Module):
    def __init__(self, lambda_heatmap=1.0, lambda_offset=0.1):
        """
        Joint loss combining Adaptive Wing Loss for heatmaps and L1 loss for offsets.
        """
        super(JointCoordinateOffsetLoss, self).__init__()
        self.heatmap_loss = AdaptiveWingLoss()
        self.lambda_heatmap = lambda_heatmap
        self.lambda_offset = lambda_offset

    def forward(self, pred_heatmaps, pred_offsets, true_heatmaps, true_offsets, peak_masks):
        """
        Args:
            pred_heatmaps: (N, C, H, W) predicted heatmaps
            pred_offsets: (N, C*2, H, W) predicted continuous offsets
            true_heatmaps: (N, C, H, W) target heatmaps
            true_offsets: (N, C*2, H, W) target continuous offsets
            peak_masks: (N, C*2, H, W) mask showing exactly the peak coordinate pixel of each active landmark
        """
        loss_h = self.heatmap_loss(pred_heatmaps, true_heatmaps)
        
        # Only compute offset L1 loss strictly at the peak coordinate locations
        # to avoid severe gradient dilution and grid-wide zero-forcing biases.
        abs_diff = torch.abs(pred_offsets - true_offsets)
        loss_o = torch.sum(abs_diff * peak_masks) / (torch.sum(peak_masks) + 1e-8)
        
        return self.lambda_heatmap * loss_h + self.lambda_offset * loss_o
