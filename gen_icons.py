from PIL import Image
import os

src_path = r"C:\Users\SER5 MAX\bantudulu\logo.png"
base = r"C:\Users\SER5 MAX\bantudulu-android\android\app\src\main\res"

src = Image.open(src_path)
print(f"Source: {src.size} {src.mode}")

sizes = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}

for folder, size in sizes.items():
    img = src.resize((size, size), Image.LANCZOS)
    path = os.path.join(base, folder, 'ic_launcher.png')
    img.save(path)
    print(f"  {folder}: {img.size} -> {path}")

# Also regenerate round icons
for folder, size in sizes.items():
    img = src.resize((size, size), Image.LANCZOS)
    path = os.path.join(base, folder, 'ic_launcher_round.png')
    img.save(path)
    print(f"  {folder} round: {img.size} -> {path}")

print("\nDONE - All icons regenerated from original logo!")
