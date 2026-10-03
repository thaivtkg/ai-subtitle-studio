import subprocess
import sys
import os

def build_app():
    print("Starting Build AI Subtitle Studio via PyInstaller...")
    
    hidden_imports = [
        "pydantic",
        "google.genai",
        "openai",
        "dotenv",
        "sqlite3",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets"
    ]
    
    datas = [
        "--add-data=resources;resources"
    ]
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AI Subtitle Studio",
        "--windowed",
        "--icon=app_icon.ico",
        "--noconfirm",
        "--clean",
    ]
    
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
        
    cmd.extend(datas)
    cmd.append("main.py")
    
    print(f"PyInstaller command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("Build success! Output in 'dist/AI Subtitle Studio/'")
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_app()
