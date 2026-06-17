import os
import sys
import traceback

# Add project root to sys.path to allow imports from any CWD
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from api.model import load_model, run_inference
from api.utils import preprocess_image, postprocess_landmarks
from api.analysis import build_analysis_report

try:
    model_path = os.path.join(project_root, 'models', 'best_model.pth')
    sample_image_path = os.path.join(project_root, 'dataset', 'test', 'Cephalograms', 'cl5lc0isc127g072u23n3bcec.jpg')
    
    model = load_model(model_path)
    with open(sample_image_path, 'rb') as f:
        contents = f.read()
    tensor, size = preprocess_image(contents)
    heatmaps = run_inference(model, tensor)
    landmarks = postprocess_landmarks(heatmaps, size)
    print('Predict success. Landmarks:', len(landmarks))
    
    analysis = build_analysis_report(landmarks, px_to_mm=0.1, ethnic_profile='Caucasian', protocol_id='core_lateral')
    print('Analysis success.')
except Exception as e:
    traceback.print_exc()
