"""
Génère l'icône officielle Lightpanda Bridge :
Panda blanc minimaliste sur fond noir profond avec micro-reliefs subtils et reflets modernes.
"""
from PIL import Image, ImageDraw, ImageFilter

def generate_panda_icon(size):
    # Rendu en haute résolution (super-échantillonnage 4x) pour des courbes ultra-lisses
    scale = 4
    w = size * scale
    img = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Fond noir profond avec coins arrondis style squircle (arrondi moderne)
    radius = int(w * 0.24)
    # Légère lueur / dégradé d'ambiance
    draw.rounded_rectangle([0, 0, w - 1, w - 1], radius=radius, fill=(11, 15, 25, 255))
    
    # 2. Bordure subtile en micro-relief (liseré lumineux supérieur)
    draw.rounded_rectangle([scale, scale, w - scale - 1, w - scale - 1], radius=radius - scale, outline=(255, 255, 255, 45), width=max(1, int(scale * 1.2)))
    
    # Reflet discret supérieur
    draw.ellipse([int(w * 0.15), -int(w * 0.2), int(w * 0.85), int(w * 0.35)], fill=(255, 255, 255, 12))

    # --- PANDA BLANC MINIMALISTE ---
    # Oreilles noires/sombres surélevées
    ear_w = int(w * 0.22)
    ear_h = int(w * 0.22)
    # Oreille gauche
    draw.ellipse([int(w * 0.17), int(w * 0.18), int(w * 0.17) + ear_w, int(w * 0.18) + ear_h], fill=(22, 27, 38, 255), outline=(255, 255, 255, 50), width=scale)
    # Oreille droite
    draw.ellipse([int(w * 0.61), int(w * 0.18), int(w * 0.61) + ear_w, int(w * 0.18) + ear_h], fill=(22, 27, 38, 255), outline=(255, 255, 255, 50), width=scale)

    # Tête blanche avec doux relief (blanc immaculé légèrement ivoire)
    head_left = int(w * 0.20)
    head_top = int(w * 0.28)
    head_right = int(w * 0.80)
    head_bottom = int(w * 0.80)
    
    # Ombre portée de la tête
    draw.ellipse([head_left, head_top + int(scale * 2), head_right, head_bottom + int(scale * 2)], fill=(0, 0, 0, 100))
    # Tête blanche
    draw.ellipse([head_left, head_top, head_right, head_bottom], fill=(255, 255, 255, 255))

    # Taches noires des yeux (inclinées caractéristiques du panda)
    patch_w = int(w * 0.15)
    patch_h = int(w * 0.19)
    # Tache gauche
    draw.ellipse([int(w * 0.30), int(w * 0.44), int(w * 0.30) + patch_w, int(w * 0.44) + patch_h], fill=(16, 20, 30, 255))
    # Tache droite
    draw.ellipse([int(w * 0.55), int(w * 0.44), int(w * 0.55) + patch_w, int(w * 0.44) + patch_h], fill=(16, 20, 30, 255))

    # Pupilles blanches minimalistes étincelantes
    pupil_size = int(w * 0.04)
    draw.ellipse([int(w * 0.36), int(w * 0.50), int(w * 0.36) + pupil_size, int(w * 0.50) + pupil_size], fill=(255, 255, 255, 255))
    draw.ellipse([int(w * 0.60), int(w * 0.50), int(w * 0.60) + pupil_size, int(w * 0.50) + pupil_size], fill=(255, 255, 255, 255))

    # Petit nez noir minimaliste
    nose_w = int(w * 0.08)
    nose_h = int(w * 0.06)
    draw.ellipse([int(w * 0.46), int(w * 0.62), int(w * 0.46) + nose_w, int(w * 0.62) + nose_h], fill=(16, 20, 30, 255))

    # Redimensionner en haute qualité
    icon = img.resize((size, size), Image.Resampling.LANCZOS)
    return icon

for sz in [16, 32, 48, 128]:
    ico = generate_panda_icon(sz)
    ico.save(f"./extension/icons/icon{sz}.png")
    print(f"Icon {sz}x{sz} générée avec succès.")
