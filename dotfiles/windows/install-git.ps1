# dotfiles install-git — 폐쇄망 Windows 에서 Git for Windows 를 오프라인 설치하고 Git Bash 를 쓸 수 있게 한다
#
# 사용법 (PowerShell):
#   powershell -ExecutionPolicy Bypass -File windows\install-git.ps1 [-Installer <설치 파일>] [-Scope User|Machine]
#                                                                    [-PortableDir <경로>] [-SkipBashrc]
#   cmd 에서는 windows\install-git.cmd 에 같은 인자를 넘긴다.
#
# 설치 파일은 인터넷이 되는 곳에서 https://git-scm.com/downloads/win (또는 github.com/git-for-windows/git/releases)
# 에서 받아 반입한다. 둘 중 하나:
#   - Git-<버전>-64-bit.exe          : 설치형. 기본은 관리자 권한 없이 사용자 단위(/CURRENTUSER) 설치
#   - PortableGit-<버전>-64-bit.7z.exe : 포터블. 압축만 풀므로 설치형이 막힌 PC 에서도 쓴다
# -Installer 를 주지 않으면 windows\offline\, windows\, ~\Downloads 순으로 찾는다 (설치형 우선, 높은 버전 우선).
#
# 동작 (섹션 번호 = 아래 주석 번호 = README 'Windows 폐쇄망 (Git Bash)' 단계 표):
#   0. 사전 검사 — 설치 파일·서명·권한·배치 원본을 확인. 실패하면 홈과 시스템을 하나도 바꾸지 않고 종료
#   1. Git 설치 — Git 이 이미 있으면 건너뜀. 설치형은 무인 설치, 포터블은 압축 해제 + post-install
#   2. PATH — <Git>\cmd 가 PATH 에 없을 때만(포터블 등) 사용자 PATH 에 추가 (설치형은 설치 파일이 직접 추가)
#   3. Git Bash 실행 경로 — Windows Terminal 이 있으면 'Git Bash' 프로필(fragment), 포터블은 시작 메뉴 바로가기
#   4. ~/.bashrc, ~/.bash_profile 배치 (gitbash/). -SkipBashrc 면 건너뜀
#   5. 확인 — git --version, Git Bash 로 ~/.bashrc 문법 검사
#
# 멱등(idempotent): 재실행해도 안전하다. 배치 파일은 내용이 다를 때만 .bak 백업 후 덮어쓴다.
# 되돌리기: windows\uninstall-git.ps1 — ~\.config\dotfiles\backup\gitbash-* 기록을 기준으로 복원한다.
#   - gitbash-<name>.orig / .absent : 배치 전 원본 / 원래 없었다는 표시 (최초 1회만 기록)
#   - gitbash-git-installed.txt     : 이 스크립트가 새로 설치한 Git (mode·경로). 원래 있던 Git 은 기록하지 않는다
#   - gitbash-path-added.txt        : 이 스크립트가 사용자 PATH 에 추가한 항목
# 홈은 $env:HOME 이 있으면 그것(Git Bash 도 그 값을 홈으로 쓴다), 없으면 $env:USERPROFILE.
#
# 이 파일은 UTF-8(BOM) 로 저장한다 — Windows PowerShell 5.1 은 BOM 이 없으면 한글을 ANSI(cp949)로 읽어 깨진다.

[CmdletBinding()]
param(
  [string]$Installer,
  [ValidateSet('User', 'Machine')][string]$Scope = 'User',
  [string]$PortableDir = (Join-Path $env:LOCALAPPDATA 'Programs\PortableGit'),
  [switch]$SkipBashrc
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Info([string]$m) { Write-Host "[install-git] $m" -ForegroundColor Cyan }
function Warn([string]$m) { Write-Host "[install-git] 경고: $m" -ForegroundColor Yellow }
function Die([string]$m)  { Write-Host "[install-git] 오류: $m" -ForegroundColor Red; exit 1 }

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$HomeDir    = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
$BackupDir  = Join-Path $HomeDir '.config\dotfiles\backup'
$WtFragment = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\dotfiles-gitbash\git-bash.json'
$StartMenuLnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Git Bash (Portable).lnk'
$Deploys = @(
  @{ Src = (Join-Path $RepoRoot 'gitbash\bashrc');       Dst = (Join-Path $HomeDir '.bashrc');       Name = 'bashrc' },
  @{ Src = (Join-Path $RepoRoot 'gitbash\bash_profile'); Dst = (Join-Path $HomeDir '.bash_profile'); Name = 'bash_profile' }
)

# 파일 이름에서 종류와 버전을 읽는다. Git-2.47.1-64-bit.exe → installer, 2.47.1 (패치 번호가 붙은 4자리 버전도 받는다)
function Get-InstallerInfo([string]$path) {
  $n = Split-Path -Leaf $path
  if ($n -match '^PortableGit-(\d+(\.\d+)+)-64-bit\.7z\.exe$') { return @{ Path = $path; Mode = 'portable';  Version = [version]$Matches[1] } }
  if ($n -match '^Git-(\d+(\.\d+)+)-64-bit\.exe$')             { return @{ Path = $path; Mode = 'installer'; Version = [version]$Matches[1] } }
  return $null
}

# 이미 설치된 Git 의 루트(bin\bash.exe 가 있는 곳). 설치형 레지스트리 → 포터블 경로 → PATH 의 git 순
function Find-GitRoot {
  foreach ($key in 'HKCU:\SOFTWARE\GitForWindows', 'HKLM:\SOFTWARE\GitForWindows') {
    $p = (Get-ItemProperty -Path $key -Name InstallPath -ErrorAction SilentlyContinue)
    if ($p -and (Test-Path (Join-Path $p.InstallPath 'bin\bash.exe'))) { return $p.InstallPath }
  }
  if (Test-Path (Join-Path $PortableDir 'bin\bash.exe')) { return $PortableDir }
  $cmd = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cmd) {
    # <root>\cmd\git.exe 또는 <root>\bin\git.exe 또는 <root>\mingw64\bin\git.exe
    $d = Split-Path -Parent $cmd.Source
    foreach ($root in (Split-Path -Parent $d), (Split-Path -Parent (Split-Path -Parent $d))) {
      if ($root -and (Test-Path (Join-Path $root 'bin\bash.exe'))) { return $root }
    }
  }
  return $null
}

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ── 0. 사전 검사 (변경 전) ───────────────────────────────
# 여기서 실패하면 ~\.config\dotfiles\backup 을 포함해 아무것도 만들거나 바꾸지 않는다.
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { Die 'Windows 전용 스크립트 — macOS/Linux/WSL 은 ./install.sh 를 쓴다' }
if (-not [Environment]::Is64BitOperatingSystem) { Die '64비트 Windows 만 지원 (Git for Windows 32비트 배포는 중단됨)' }
if (-not (Test-Path $HomeDir)) { Die "홈 디렉터리 없음: $HomeDir" }
if (-not $SkipBashrc) {
  foreach ($d in $Deploys) { if (-not (Test-Path $d.Src)) { Die "배치 원본 없음: $($d.Src) — 저장소 전체를 반입했는지 확인" } }
}

$GitRoot = Find-GitRoot
$Pkg = $null
if ($GitRoot) {
  Info "Git 이 이미 있음: $GitRoot — 설치는 건너뛰고 Git Bash 환경만 맞춘다"
} else {
  if ($Installer) {
    if (-not (Test-Path $Installer)) { Die "설치 파일 없음: $Installer" }
    $Pkg = Get-InstallerInfo (Resolve-Path $Installer).Path
    if (-not $Pkg) { Die "설치 파일 이름이 Git-<버전>-64-bit.exe 또는 PortableGit-<버전>-64-bit.7z.exe 가 아님: $Installer" }
  } else {
    $dirs = @((Join-Path $PSScriptRoot 'offline'), $PSScriptRoot, (Join-Path $env:USERPROFILE 'Downloads'))
    $found = @(foreach ($d in $dirs) {
      if (Test-Path $d) { Get-ChildItem -Path $d -File -Filter '*.exe' | ForEach-Object { Get-InstallerInfo $_.FullName } }
    }) | Where-Object { $_ }
    # 설치형 우선(시작 메뉴·탐색기 메뉴·제거 프로그램까지 갖춰진다), 같은 종류면 높은 버전
    $Pkg = $found | Sort-Object @{ Expression = { $_.Mode -eq 'installer' }; Descending = $true }, @{ Expression = { $_.Version }; Descending = $true } | Select-Object -First 1
    if (-not $Pkg) {
      Die ("Git 설치 파일을 찾지 못함 — 인터넷이 되는 PC 에서 Git-<버전>-64-bit.exe 또는 PortableGit-<버전>-64-bit.7z.exe 를 받아 " +
           "windows\offline\ 에 두거나 -Installer 로 지정 (홈 파일은 변경하지 않았음)")
    }
  }
  Info "설치 파일: $($Pkg.Path) ($($Pkg.Mode), $($Pkg.Version))"

  # 서명 검사 — 반입 과정에서 바뀐 파일을 막는다. 폐쇄망에서는 인증서 폐기 목록을 못 받아 Valid 가 아닐 수 있어
  # 서명이 없거나 해시가 틀린 경우만 중단하고 나머지는 경고한다.
  $sig = Get-AuthenticodeSignature -FilePath $Pkg.Path
  switch ($sig.Status) {
    'Valid'        { Info "서명 확인: $($sig.SignerCertificate.Subject)" }
    'NotSigned'    { Die '설치 파일에 서명이 없음 — 공식 배포 파일이 아니다 (홈 파일은 변경하지 않았음)' }
    'HashMismatch' { Die '설치 파일 서명과 내용이 다름 — 반입 중 손상·변조 (홈 파일은 변경하지 않았음)' }
    default        { Warn "서명 상태 $($sig.Status) ($($sig.StatusMessage)) — 폐쇄망의 인증서 검증 제약일 수 있다. 아래 SHA-256 을 공식 릴리스 페이지 값과 대조할 것" }
  }
  Info "SHA-256: $((Get-FileHash -Algorithm SHA256 -Path $Pkg.Path).Hash)"

  if ($Pkg.Mode -eq 'installer' -and $Scope -eq 'Machine' -and -not (Test-Admin)) {
    Die '-Scope Machine 은 관리자 PowerShell 에서 실행해야 함 — 권한이 없으면 기본값(User) 또는 PortableGit 을 쓴다 (홈 파일은 변경하지 않았음)'
  }
  if ($Pkg.Mode -eq 'portable' -and (Test-Path $PortableDir) -and (Get-ChildItem -Force $PortableDir | Select-Object -First 1)) {
    Die "포터블 설치 경로가 비어 있지 않음: $PortableDir — 비우거나 -PortableDir 로 다른 경로 지정 (홈 파일은 변경하지 않았음)"
  }
}

# 이전 버전이 쓰던 ~\.dotfiles-backup 이 남아 있으면 새 위치로 옮긴다
$LegacyBackupDir = Join-Path $HomeDir '.dotfiles-backup'
if ((Test-Path $LegacyBackupDir) -and -not (Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BackupDir) | Out-Null
  Move-Item -LiteralPath $LegacyBackupDir -Destination $BackupDir
  Info "~\.dotfiles-backup -> $BackupDir 이동"
}
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

function Write-Utf8NoBom([string]$path, [string]$text) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
  [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
}

# manifest 에 한 줄 추가 (중복 없이)
function Add-Record([string]$file, [string]$line) {
  $p = Join-Path $BackupDir $file
  if ((Test-Path $p) -and ((Get-Content -LiteralPath $p) -contains $line)) { return }
  Add-Content -LiteralPath $p -Value $line -Encoding UTF8
}

# ── 1. Git 설치 ─────────────────────────────────────────
if (-not $GitRoot) {
  if ($Pkg.Mode -eq 'installer') {
    $log = Join-Path $env:TEMP 'dotfiles-git-install.log'
    $scopeArg = if ($Scope -eq 'Machine') { '/ALLUSERS' } else { '/CURRENTUSER' }
    # /o: 는 Git for Windows 설치 파일의 옵션 지정 방식. PathOption=Cmd 는 git 만 PATH 에 넣고(유닉스 도구는 넣지 않음)
    # CURLOption=WinSSL 은 Windows 인증서 저장소를 써서 사내 CA 로 서명된 내부 Git 서버에도 붙게 한다.
    $argv = @('/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-', '/SUPPRESSMSGBOXES', $scopeArg, "/LOG=`"$log`"",
              '/o:PathOption=Cmd', '/o:CURLOption=WinSSL', '/o:EditorOption=VIM', '/o:BashTerminalOption=MinTTY')
    Info "Git 설치 중 ($Scope, 무인) — 로그: $log"
    $p = Start-Process -FilePath $Pkg.Path -ArgumentList $argv -Wait -PassThru
    if ($p.ExitCode -ne 0) { Die "설치 파일 종료 코드 $($p.ExitCode) — 로그 확인: $log (권한 문제면 PortableGit-<버전>-64-bit.7z.exe 로 다시 실행)" }
    $GitRoot = Find-GitRoot
    if (-not $GitRoot) { Die "설치는 끝났지만 Git 경로를 찾지 못함 — 로그 확인: $log" }
    Add-Record 'gitbash-git-installed.txt' 'mode=installer'
    Add-Record 'gitbash-git-installed.txt' "path=$GitRoot"
  } else {
    Info "PortableGit 압축 해제 → $PortableDir"
    New-Item -ItemType Directory -Force -Path $PortableDir | Out-Null
    # 설치 기록을 먼저 남긴다 — 압축 해제가 중간에 실패해도 uninstall -Purge 로 치울 수 있게
    Add-Record 'gitbash-git-installed.txt' 'mode=portable'
    Add-Record 'gitbash-git-installed.txt' "path=$PortableDir"
    $p = Start-Process -FilePath $Pkg.Path -ArgumentList @("-o`"$PortableDir`"", '-y') -Wait -PassThru
    if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $PortableDir 'bin\bash.exe'))) { Die "압축 해제 실패 (종료 코드 $($p.ExitCode))" }
    # 첫 실행 초기화 스크립트. 압축 해제가 이미 돌렸으면 스스로 지워져 없다
    if (Test-Path (Join-Path $PortableDir 'post-install.bat')) {
      Info 'post-install.bat 실행'
      Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\cmd.exe') -ArgumentList @('/d', '/c', 'post-install.bat') `
        -WorkingDirectory $PortableDir -WindowStyle Hidden -Wait | Out-Null
    }
    $GitRoot = $PortableDir
  }
  Info "Git 설치 완료: $GitRoot"
}

# ── 2. PATH ─────────────────────────────────────────────
# 설치형은 PathOption=Cmd 로 설치 파일이 직접 넣는다. 포터블이나 PATH 에 없는 기존 Git 일 때만 사용자 PATH 에 <root>\cmd 를 추가한다.
$CmdDir = Join-Path $GitRoot 'cmd'
# 설치형 직후에는 이 창의 PATH 가 갱신되지 않았으므로 레지스트리(사용자·시스템 PATH)까지 본다
function Test-InPath([string]$dir) {
  $norm = { param($s) ([Environment]::ExpandEnvironmentVariables($s)).TrimEnd('\') }
  $user = (Get-Item 'HKCU:\Environment').GetValue('Path', '', 'DoNotExpandEnvironmentNames')
  $machine = (Get-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').GetValue('Path', '', 'DoNotExpandEnvironmentNames')
  $all = @("$machine;$user;$env:Path" -split ';' | Where-Object { $_ } | ForEach-Object { & $norm $_ })
  return $all -contains (& $norm $dir)
}
if (-not (Test-InPath $CmdDir) -and -not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
  $envKey = Get-Item -Path 'HKCU:\Environment'
  $cur = $envKey.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
  $parts = @($cur -split ';' | Where-Object { $_ })
  if ($parts -notcontains $CmdDir) {
    # 원래 값의 종류(REG_EXPAND_SZ 의 %VAR%)를 보존하려고 [Environment] 대신 레지스트리에 직접 쓴다
    $kind = if ($cur) { $envKey.GetValueKind('Path') } else { 'ExpandString' }
    Set-ItemProperty -Path 'HKCU:\Environment' -Name Path -Value (($parts + $CmdDir) -join ';') -Type $kind
    Add-Record 'gitbash-path-added.txt' $CmdDir
    # 새로 여는 창이 바뀐 PATH 를 읽도록 WM_SETTINGCHANGE 를 보낸다 (없는 변수를 지우는 호출이 알림만 보낸다)
    [Environment]::SetEnvironmentVariable('DOTFILES_GITBASH_REFRESH', $null, 'User')
    Info "사용자 PATH 에 추가: $CmdDir (새로 여는 cmd/PowerShell 창부터 적용)"
  }
}
if (@($env:Path -split ';') -notcontains $CmdDir) { $env:Path = "$env:Path;$CmdDir" }

# ── 3. Git Bash 실행 경로 ───────────────────────────────
$BashExe = Join-Path $GitRoot 'bin\bash.exe'
$GitBashExe = Join-Path $GitRoot 'git-bash.exe'
$Icon = Join-Path $GitRoot 'mingw64\share\git\git-for-windows.ico'
$hasWt = (Get-Command wt.exe -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\wt.exe'))
# 설치 파일의 windowsterminal 구성 요소가 이미 프로필을 넣었으면 중복을 만들지 않는다
$gitOwnFragment = Test-Path (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\Git')
if ($hasWt -and -not $gitOwnFragment) {
  $wtProfile = [ordered]@{
    guid              = '{8f3a6c1e-5b7d-4e2a-9c41-2d6b0f7e9a13}'
    name              = 'Git Bash'
    commandline       = "`"$BashExe`" -i -l"
    startingDirectory = '%USERPROFILE%'
  }
  if (Test-Path $Icon) { $wtProfile.icon = $Icon }
  $json = ConvertTo-Json -Depth 5 @{ profiles = @($wtProfile) }
  if (-not (Test-Path $WtFragment) -or ([IO.File]::ReadAllText($WtFragment) -ne $json)) {
    Write-Utf8NoBom $WtFragment $json
    Info "Windows Terminal 에 'Git Bash' 프로필 추가 (터미널을 다시 열면 보인다)"
  }
} elseif (-not $hasWt) {
  Info 'Windows Terminal 없음 — 프로필 추가 건너뜀'
}
# 포터블은 시작 메뉴 항목이 없으므로 만든다 (설치형은 설치 파일이 만든다)
if (($GitRoot -eq $PortableDir) -and -not (Test-Path $StartMenuLnk)) {
  try {
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut($StartMenuLnk)
    $lnk.TargetPath = $GitBashExe
    $lnk.Arguments = '--cd-to-home'
    $lnk.WorkingDirectory = $HomeDir
    if (Test-Path $Icon) { $lnk.IconLocation = $Icon }
    $lnk.Save()
    Info "시작 메뉴 바로가기: $StartMenuLnk"
  } catch {
    Warn "시작 메뉴 바로가기를 만들지 못함 ($($_.Exception.Message)) — $GitBashExe 를 직접 실행"
  }
}

# ── 4. ~/.bashrc, ~/.bash_profile ───────────────────────
function Deploy-File([string]$src, [string]$dst, [string]$name) {
  $orig = Join-Path $BackupDir "gitbash-$name.orig"
  $absent = Join-Path $BackupDir "gitbash-$name.absent"
  # 최초 실행 시에만 원본 상태를 기록
  if (-not (Test-Path $orig) -and -not (Test-Path $absent)) {
    if (Test-Path $dst) { Copy-Item -LiteralPath $dst -Destination $orig } else { New-Item -ItemType File -Path $absent | Out-Null }
  }
  if (Test-Path $dst) {
    if ((Get-FileHash -LiteralPath $src).Hash -eq (Get-FileHash -LiteralPath $dst).Hash) { return }
    Copy-Item -LiteralPath $dst -Destination "$dst.bak" -Force
    Info "기존 $(Split-Path -Leaf $dst) → .bak 백업"
  }
  # 바이트 그대로 복사 — 줄바꿈이 CRLF 로 바뀌면 bash 가 읽지 못한다
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Info "$dst 배치"
}
if ($SkipBashrc) {
  Info '-SkipBashrc — ~/.bashrc 배치 건너뜀'
} else {
  foreach ($d in $Deploys) { Deploy-File $d.Src $d.Dst $d.Name }
  if (-not (Test-Path (Join-Path $HomeDir '.bashrc.local'))) {
    Info '머신별 alias/함수는 ~/.bashrc.local 에 둔다 (이 스크립트는 만들지 않음)'
  }
}

# ── 5. 확인 ─────────────────────────────────────────────
Info ((& (Join-Path $CmdDir 'git.exe') --version) -join ' ')
if (-not $SkipBashrc) {
  & $BashExe -n (Join-Path $HomeDir '.bashrc')
  if ($LASTEXITCODE -ne 0) { Warn '~/.bashrc 문법 오류 — 줄바꿈이 CRLF 로 바뀌었는지 확인' }
}
Info "완료. Git Bash 실행: 시작 메뉴 'Git Bash', Windows Terminal 'Git Bash' 프로필, 또는 `"$GitBashExe`""
