# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

# Xác định thư mục gốc của project (lùi 1 cấp từ thư mục build/)
project_root = os.path.abspath(os.path.join(SPECPATH, '..'))

# 1. Thu thập data files & dynamic libs từ các thư viện AI
datas = []
datas += collect_data_files('faster_whisper')
datas += collect_data_files('ctranslate2')
datas += collect_data_files('huggingface_hub')
datas += collect_data_files('tokenizers')

# [QUAN TRỌNG] Đóng gói FFmpeg và Resources theo đúng Contract của RuntimePaths
ffmpeg_dir = os.path.join(project_root, 'ffmpeg')
resources_dir = os.path.join(project_root, 'resources')

if os.path.exists(ffmpeg_dir):
    datas.append((ffmpeg_dir, 'ffmpeg'))
if os.path.exists(resources_dir):
    datas.append((resources_dir, 'resources'))

binaries = []
binaries += collect_dynamic_libs('ctranslate2')

# 2. Hidden imports để tránh lỗi thiếu module ngầm của PySide6, PyTorch và nội bộ
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'faster_whisper',
    'ctranslate2',
    'huggingface_hub',
    'tokenizers',
    'torch',
    'torchaudio',
    'psutil',
    'unittest.mock',  # Đã ghim cứng để sửa lỗi PyTorch Import
    # Modules nội bộ của dự án
    'core',
    'core.artifacts',
    'core.project',
    'core.runtime',
    'core.services',
    'core.timing',
    'player',
    'ui',
    'workers',
]
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('ctranslate2')

# 3. Phân tích mã nguồn
a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # LƯU Ý: Không loại trừ 'unittest' vì PyTorch cần nó
    excludes=['tkinter', 'pytest', 'IPython', 'notebook'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Load Icon cho file EXE
icon_file = os.path.join(project_root, 'resources', 'app_icon.ico')

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI Subtitle Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Đặt False để ẩn cửa sổ CMD đen khi chạy App
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if os.path.exists(icon_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AI Subtitle Studio',
)