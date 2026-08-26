Write-Host "--- [DỌN DẸP THƯ MỤC BUILD & CACHE] ---" -ForegroundColor Yellow

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."

Remove-Item -Path "$ProjectRoot\build\ai_subtitle_studio" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$ProjectRoot\dist\AI Subtitle Studio" -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path "$ProjectRoot" -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path "$ProjectRoot" -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Đã dọn dẹp sạch các thư mục tạm." -ForegroundColor Green