import urllib.request
import os
import zipfile
import shutil
import sys

# Download JDK 21 for Windows x64
# Download JDK 21 for Windows x64 - use Azul Zulu (smaller, faster CDN)
url = "https://cdn.azul.com/zulu/bin/zulu21.40.19-ca-jdk21.0.7-win_x64.zip"
print(f"Downloading JDK 21 from {url}...")

try:
    dl_path = r"C:\Users\SER5 MAX\bantudulu\jdk21.zip"
    urllib.request.urlretrieve(url, dl_path)
    print(f"Downloaded: {os.path.getsize(dl_path)} bytes")
    
    # Extract
    extract_to = r"C:\Users\SER5 MAX\bantudulu\jdk21"
    print("Extracting...")
    with zipfile.ZipFile(dl_path, 'r') as zf:
        zf.extractall(extract_to)
    
    # Find java.exe
    for root, dirs, files in os.walk(extract_to):
        if 'java.exe' in files:
            java_home = root.replace('\\bin', '')
            print(f"\nJDK installed at: {java_home}")
            
            # Write gradle.properties
            prop_path = r"C:\Users\SER5 MAX\bantudulu-android\android\gradle.properties"
            with open(prop_path, 'a') as f:
                f.write(f"\norg.gradle.java.home={java_home}\n")
            print(f"Updated: {prop_path}")
            
            # Verify
            import subprocess
            result = subprocess.run([os.path.join(root, 'java.exe'), '-version'], capture_output=True, text=True)
            print(f"Java: {result.stderr.strip()}")
            break
    
    # Cleanup
    os.remove(dl_path)
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
