import pytest
from api.growth_stage import estimate_cvm_stage_from_morphology

def build_mock_vertebra(name_prefix: str, ip_y=0.0, ia_y=0.0, i_y=0.0, sp_y=-10.0, sa_y=-10.0, width=15.0):
    # ip at x=0, ia at x=width, i at x=width/2
    # sp at x=0, sa at x=width
    # vertical coordinates are y
    return [
        {"name": f"{name_prefix}_IP", "x": 0.0, "y": ip_y},
        {"name": f"{name_prefix}_IA", "x": width, "y": ia_y},
        {"name": f"{name_prefix}_I", "x": width / 2.0, "y": i_y},
        {"name": f"{name_prefix}_SP", "x": 0.0, "y": sp_y},
        {"name": f"{name_prefix}_SA", "x": width, "y": sa_y},
    ]

def test_cvm_stage_1_flat_borders():
    # C2, C3, C4 all flat: i_y equals or is below (larger y) the corners.
    # Height-to-width ratio: w = 15.0, average height = 10.0. Ratio = 10/15 = 0.67 (horizontal).
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=0.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=0.0))
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=0.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 1

def test_cvm_stage_2_c2_concave():
    # C2 is concave (i_y curves up by 2.0 pixels), others are flat.
    # concavity depth = 2.0 mm >= 1.0 mm.
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=0.0))
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=0.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 2

def test_cvm_stage_3_c2_c3_concave():
    # C2 and C3 concave, C4 flat.
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=0.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 3

def test_cvm_stage_4_all_concave_horizontal():
    # C2, C3, C4 all concave.
    # C3 and C4 shapes are horizontal: w = 15.0, h = 10.0, ratio = 0.67 < 0.90.
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-10.0, sa_y=-10.0))
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-10.0, sa_y=-10.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 4

def test_cvm_stage_5_all_concave_square():
    # C2, C3, C4 all concave.
    # C3 and C4 are square: w = 10.0, h = 10.0, ratio = 1.0 (between 0.90 and 1.15).
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    # width=10, height=10
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-10.0, sa_y=-10.0, width=10.0))
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-10.0, sa_y=-10.0, width=10.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 5

def test_cvm_stage_6_all_concave_vertical():
    # C2, C3, C4 all concave.
    # At least one vertebra is vertical: w = 8.0, h = 12.0, ratio = 1.5 > 1.15.
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-10.0, sa_y=-10.0, width=10.0)) # square
    landmarks.extend(build_mock_vertebra("C4", ip_y=0.0, ia_y=0.0, i_y=-2.0, sp_y=-12.0, sa_y=-12.0, width=8.0))   # vertical
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage == 6

def test_cvm_insufficient_data():
    # Missing C4 landmarks
    landmarks = []
    landmarks.extend(build_mock_vertebra("C2", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    landmarks.extend(build_mock_vertebra("C3", ip_y=0.0, ia_y=0.0, i_y=-2.0))
    
    stage = estimate_cvm_stage_from_morphology(landmarks, px_to_mm=1.0)
    assert stage is None
