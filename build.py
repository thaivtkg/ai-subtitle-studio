import subprocess
import sys
import os

def build_app():
    print("==================================================")
    print(" BẮT ĐẦU QUY TRÌNH ĐÓNG GÓI AI SUBTITLE STUDIO    ")
    print("==================================================")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    spec_path = os.path.join(project_root, "AI Subtitle Studio.spec")
    
    if os.path.exists(spec_path):
        cmd = [
            sys.executable, "-m", "PyInstaller",
            spec_path,
            "--noconfirm",
            "--clean"
        ]
    else:
        hidden_imports = [
            "PySide6.QtCore",
            "PySide6.QtGui",
            "PySide6.QtWidgets",
            "PySide6.QtMultimedia",
            "PySide6.QtMultimediaWidgets",
            "pydantic",
            "sqlite3",
            "faster_whisper",
            "ctranslate2",
            "torch",
            "torchaudio",
            "psutil"
        ]
        datas = ["--add-data=resources;resources"]
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name=AI Subtitle Studio",
            "--windowed",
            "--icon=resources/app_icon.ico",
            "--noconfirm",
            "--clean",
        ]
        for imp in hidden_imports:
            cmd.append(f"--hidden-import={imp}")
        cmd.extend(datas)
        cmd.append("main.py")
        
    print(f"PyInstaller command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True, cwd=project_root)
        print("\n✅ Build thành công! Thư mục kết xuất: 'dist/AI Subtitle Studio/'")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build thất bại: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_app()
