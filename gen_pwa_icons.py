from PIL import Image
import os

src_path = r"C:\Users\SER5 MAX\bantudulu\logo.png"
pwa_dir = r"C:\Users\SER5 MAX\bantudulu\app\static\images\pwa"

src = Image.open(src_path)
print(f"Source: {src.size}")

sizes = {
    'icon-72x72.png': 72,
    'icon-96x96.png': 96,
    'icon-128x128.png': 128,
    'icon-144x144.png': 144,
    'icon-152x152.png': 152,
    'icon-192x192.png': 192,
    'icon-384x384.png': 384,
    'icon-512x512.png': 512,
    'apple-touch-icon.png': 180,
}

for name, size in sizes.items():
    img = src.resize((size, size), Image.LANCZOS)
    path = os.path.join(pwa_dir, name)
    img.save(path)
    print(f"  {name}: {img.size}")

print("\nDONE - All PWA icons regenerated!")
