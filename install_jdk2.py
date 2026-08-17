import urllib.request
import os
import sys
import zipfile
import subprocess
import shutil

# Try a smaller JDK - Liberica JDK from BellSoft
urls = [
    "https://download.bell-sw.com/java/21.0.6+11/bellsoft-jdk21.0.6+11-windows-amd64.zip",
    "https://github.com/bell-sw/Liberica/releases/download/21.0.6+11/bellsoft-jdk21.0.6+11-windows-amd64.zip",
]

for url in urls:
    print(f"Trying: {url}")
    try:
        dl_path = r"C:\Users\SER5 MAX\bantudulu\jdk21.zip"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as response:
            with open(dl_path, 'wb') as f:
                chunk_size = 8192
                downloaded = 0
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (chunk_size * 100) == 0:
                        print(f"  Downloaded: {downloaded:,} bytes")
        size = os.path.getsize(dl_path)
        print(f"Downloaded: {size:,} bytes")
        
        # Extract
        extract_to = r"C:\Users\SER5 MAX\bantudulu\jdk21"
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to)
        
        print("Extracting...")
        with zipfile.ZipFile(dl_path, 'r') as zf:
            zf.extractall(extract_to)
        
        # Find java.exe
        for root, dirs, files in os.walk(extract_to):
            if 'java.exe' in files:
                java_bin = root
                java_home = root.replace('\\bin', '')
                print(f"JDK at: {java_home}")
                
                # Set system PATH and JAVA_HOME for this session
                os.environ['JAVA_HOME'] = java_home
                os.environ['PATH'] = java_bin + ';' + os.environ.get('PATH', '')
                
                # Verify
                result = subprocess.run([os.path.join(java_bin, 'java.exe'), '-version'], capture_output=True, text=True)
                print(f"Java version: {result.stderr.strip()}")
                
                # Write to gradle.properties
                prop_path = r"C:\Users\SER5 MAX\bantudulu-android\android\gradle.properties"
                with open(prop_path, 'a') as f:
                    f.write(f"\norg.gradle.java.home={java_home}\n")
                print(f"Updated gradle.properties")
                
                print(f"\nJAVA_HOME={java_home}")
                open(r"C:\Users\SER5 MAX\bantudulu\java_home.txt", 'w').write(java_home)
                
                os.remove(dl_path)
                print("\nSUCCESS!")
                sys.exit(0)
                break
        
        print("java.exe not found in extracted files")
        
    except Exception as e:
        print(f"Failed: {e}")
        # Clean partial download
        if os.path.exists(dl_path):
            os.remove(dl_path)
        continue

print("All download attempts failed")
sys.exit(1)
