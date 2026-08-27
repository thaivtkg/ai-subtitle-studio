Write-Host "--- [KIEM TRA TINH TOAN VEN BAN PACKAGED BUILD] ---" -ForegroundColor Cyan

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$DistDir = "$ProjectRoot\dist\AI Subtitle Studio"

$RequiredFiles = @(
    "$DistDir\AI Subtitle Studio.exe",
    "$DistDir\_internal\ffmpeg\ffmpeg.exe",
    "$DistDir\_internal\ffmpeg\ffprobe.exe",
    "$DistDir\_internal\resources\app_icon.ico"
)

$HasError = $false

if (-not (Test-Path $DistDir)) {
    Write-Host "LOI: Thu muc dist khong ton tai!" -ForegroundColor Red
    exit 1
}

foreach ($file in $RequiredFiles) {
    if (Test-Path $file) {
        Write-Host "[OK] Tim thay: $file" -ForegroundColor Green
    } else {
        $Alternative = $file.Replace("_internal\", "")
        if (Test-Path $Alternative) {
            Write-Host "[OK] Tim thay (Root): $Alternative" -ForegroundColor Green
        } else {
            Write-Host "[THIEU] Khong tim thay: $file" -ForegroundColor Red
            $HasError = $true
        }
    }
}

if ($HasError) {
    Write-Host "`nBan build CHUA DAT chuan dong goi. Vui long kiem tra lai file spec!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nBan build hoan toan DAT CHUAN de chay thu nghiem!" -ForegroundColor Green
    exit 0
}