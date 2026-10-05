param([string]$Project = (Split-Path -Parent $MyInvocation.MyCommand.Path))
$ErrorActionPreference = "Stop"

# 项目自检：查找 pythonw（venv 优先，其次打包版 exe）
$pythonw = Join-Path $Project ".venv\Scripts\pythonw.exe"
$target = $pythonw
$arguments = "`"$Project\main.py`""
if (-not (Test-Path $pythonw)) {
    $rt = Get-ChildItem (Join-Path $Project "绿色版\runtime") -Directory -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($rt) {
        $target = Join-Path $rt.FullName "pythonw.exe"
        $arguments = "\"$Project\main.py\""
    } else {
        Write-Error "未找到 .venv 或打包 exe"
        exit 1
    }
}

$sendto = [Environment]::GetFolderPath("ApplicationData") + "\Microsoft\Windows\SendTo"
$lnkPath = Join-Path $sendto "万能格式转换器.lnk"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $target
$lnk.Arguments = $arguments
$lnk.WorkingDirectory = $Project
$lnk.IconLocation = Join-Path $Project "assets\icon.ico"
$lnk.Description = "把文件发送到万能格式转换器"
$lnk.Save()

Write-Output "已创建: $lnkPath"
Write-Output "目标: $target $arguments"
exit 0
