import os
import sys

# Add project root to sys.path to allow imports from any CWD
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from api.model import load_model, run_inference
from api.utils import preprocess_image, postprocess_landmarks

model_path = os.path.join(project_root, 'models', 'best_model.pth')
ref_image_path = os.path.join(project_root, 'references', 'Ref.jpeg')

m = load_model(model_path)
with open(ref_image_path, 'rb') as f:
    b = f.read()

tensor, orig = preprocess_image(b)
heatmaps = run_inference(m, tensor)
landmarks = postprocess_landmarks(heatmaps, orig)
print('Original size:', orig)
print('num_landmarks', len(landmarks))
print('sample', landmarks[:2])
