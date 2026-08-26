$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " BẮT ĐẦU QUY TRÌNH ĐÓNG GÓI AI SUBTITLE STUDIO    " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

# 1. Clean
& "$PSScriptRoot\clean_build.ps1"

# 2. PyInstaller Build
Write-Host "`n[1/3] Đang biên dịch PyInstaller..." -ForegroundColor Yellow
pyinstaller --noconfirm "$ProjectRoot\build\ai_subtitle_studio.spec"

# 3. Verify Package Structure
Write-Host "`n[2/3] Kiểm tra tính toàn vẹn gói..." -ForegroundColor Yellow
& "$PSScriptRoot\verify_package.ps1"

# 4. Inno Setup Build (Pipeline Automation)
Write-Host "`n[3/3] Đang tạo file Setup.exe (Inno Setup)..." -ForegroundColor Yellow
$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $ISCC) {
    & $ISCC "$ProjectRoot\installer\setup.iss"
    Write-Host "`n✅ PIPELINE HOÀN TẤT! File cài đặt nằm tại thư mục 'release\'" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ BỎ QUA BƯỚC 3: Không tìm thấy Inno Setup tại $ISCC." -ForegroundColor Red
}