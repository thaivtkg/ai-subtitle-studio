$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " BẮT ĐẦU QUY TRÌNH ĐÓNG GÓI AI SUBTITLE STUDIO    " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

# 1. Dọn dẹp cache cũ
& "$PSScriptRoot\clean_build.ps1"

# 2. Chạy PyInstaller với file spec
Write-Host "`nĐang tiến hành biên dịch qua PyInstaller..." -ForegroundColor Yellow
pyinstaller --noconfirm "$ProjectRoot\build\ai_subtitle_studio.spec"

# 3. Kiểm tra tính toàn vẹn
& "$PSScriptRoot\verify_package.ps1"

Write-Host "`nHoàn tất! Thư mục ứng dụng sẵn sàng tại: dist\AI Subtitle Studio\" -ForegroundColor Green