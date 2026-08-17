import zipfile
import os
import shutil

apk_path = r"C:\Users\SER5 MAX\bantudulu-android\android\app\build\outputs\apk\debug\app-debug.apk"
apk_out = r"C:\Users\SER5 MAX\bantudulu-android\android\app\build\outputs\apk\debug\bantudulu-v4.apk"
res_base = r"C:\Users\SER5 MAX\bantudulu-android\android\app\src\main\res"

density_map = {
    "mipmap-mdpi": "res/mipmap-mdpi",
    "mipmap-hdpi": "res/mipmap-hdpi",
    "mipmap-xhdpi": "res/mipmap-xhdpi",
    "mipmap-xxhdpi": "res/mipmap-xxhdpi",
    "mipmap-xxxhdpi": "res/mipmap-xxxhdpi",
}

shutil.copy2(apk_path, apk_out)

with zipfile.ZipFile(apk_out, 'r') as zin:
    entries = zin.namelist()
    print(f"APK entries: {len(entries)}")

# Find and replace icon entries
with zipfile.ZipFile(apk_out, 'r') as zin:
    with zipfile.ZipFile(apk_out + ".tmp", 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            is_icon = False
            for folder, apk_prefix in density_map.items():
                if item.filename == f"{apk_prefix}/ic_launcher.png" or item.filename == f"{apk_prefix}/ic_launcher_round.png":
                    is_icon = True
                    icon_name = item.filename.split("/")[-1]
                    source_path = os.path.join(res_base, folder, icon_name)
                    if os.path.exists(source_path):
                        zout.write(source_path, item.filename)
                        print(f"  Replaced: {item.filename}")
                    break
            if not is_icon:
                zout.writestr(item, zin.read(item.filename))

shutil.move(apk_out + ".tmp", apk_out)
size = os.path.getsize(apk_out)
print(f"\nAPK updated: {apk_out}")
print(f"Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
