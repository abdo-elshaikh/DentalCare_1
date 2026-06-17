"""Canonical cephalometric landmark definitions."""

LANDMARK_NAMES: dict[int, str] = {
    1: "Sella (S)", 2: "Nasion (N)", 3: "Orbitale (Or)", 4: "Porion (Po)",
    5: "Subspinale (A-point)", 6: "Supramentale (B-point)", 7: "Pogonion (Pog)",
    8: "Menton (Me)", 9: "Gnathion (Gn)", 10: "Gonion (Go)",
    11: "Lower Incisor Tip (LIT)", 12: "Upper Incisor Tip (UIT)",
    13: "Upper Lip (UL)", 14: "Lower Lip (LL)", 15: "Subnasale (Sn)",
    16: "Soft Tissue Pogonion (Pog')", 17: "Posterior Nasal Spine (PNS)",
    18: "Anterior Nasal Spine (ANS)", 19: "Articulare (Ar)",
}

LANDMARK_SHORTS: dict[int, str] = {
    1: "S", 2: "N", 3: "Or", 4: "Po", 5: "A", 6: "B", 7: "Pog", 8: "Me", 9: "Gn",
    10: "Go", 11: "LIT", 12: "UIT", 13: "UL", 14: "LL", 15: "Sn",
    16: "Pog'", 17: "PNS", 18: "ANS", 19: "Ar",
}
