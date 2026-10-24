# dotfiles uninstall-git — windows\install-git.ps1 이 적용한 것을 되돌린다
#
# 사용법 (PowerShell):
#   powershell -ExecutionPolicy Bypass -File windows\uninstall-git.ps1 [-Purge] [-KeepBackup]
#   cmd 에서는 windows\uninstall-git.cmd 에 같은 인자를 넘긴다.
#
#   (인자 없음)   : ~/.bashrc·~/.bash_profile 복원, Windows Terminal 프로필·시작 메뉴 바로가기 제거, 추가한 PATH 항목 제거
#   -Purge       : 위에 더해 install-git.ps1 이 새로 설치했다고 기록한 Git 만 제거 (원래 있던 Git 은 건드리지 않는다)
#   -KeepBackup  : ~\.config\dotfiles\backup 의 gitbash-* 기록을 남긴다 (기본은 복원 후 삭제)
#
# 복원 기준은 install-git.ps1 이 최초 실행 때 ~\.config\dotfiles\backup\ 에 남긴 gitbash-* 기록:
#   gitbash-<name>.orig → 그 내용으로 복원 / .absent → 파일 삭제 / 기록 없음 → 건드리지 않음
# ~/.bashrc.local 은 사용자 파일이라 건드리지 않는다. 멱등: 재실행해도 안전하다.
#
# 이 파일은 UTF-8(BOM) 로 저장한다 — Windows PowerShell 5.1 은 BOM 이 없으면 한글을 ANSI(cp949)로 읽어 깨진다.

[CmdletBinding()]
param(
  [switch]$Purge,
  [switch]$KeepBackup
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Info([string]$m) { Write-Host "[uninstall-git] $m" -ForegroundColor Yellow }
function Warn([string]$m) { Write-Host "[uninstall-git] 경고: $m" -ForegroundColor Red }

$HomeDir    = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
$BackupDir  = Join-Path $HomeDir '.config\dotfiles\backup'
# 이전 버전이 쓰던 ~\.dotfiles-backup 에 기록이 있으면 새 위치로 옮겨 그 기록으로 복원한다
$LegacyBackupDir = Join-Path $HomeDir '.dotfiles-backup'
if ((Test-Path $LegacyBackupDir) -and -not (Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BackupDir) | Out-Null
  Move-Item -LiteralPath $LegacyBackupDir -Destination $BackupDir
}
$WtFragmentDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\dotfiles-gitbash'
$StartMenuLnk  = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Git Bash (Portable).lnk'

# ── 1. ~/.bashrc, ~/.bash_profile 복원 ──────────────────
foreach ($name in 'bashrc', 'bash_profile') {
  $dst = Join-Path $HomeDir ".$name"
  $orig = Join-Path $BackupDir "gitbash-$name.orig"
  $absent = Join-Path $BackupDir "gitbash-$name.absent"
  if (Test-Path $orig) {
    Copy-Item -LiteralPath $orig -Destination $dst -Force
    Info "$dst ← 설치 전 원본 복원"
  } elseif (Test-Path $absent) {
    if (Test-Path $dst) { Remove-Item -LiteralPath $dst -Force; Info "$dst 삭제 (설치 전에는 없던 파일)" }
  }
  if ((Test-Path $orig) -or (Test-Path $absent)) { Remove-Item -LiteralPath "$dst.bak" -Force -ErrorAction SilentlyContinue }
}
if (Test-Path (Join-Path $HomeDir '.bashrc.local')) { Info '~/.bashrc.local 은 사용자 파일 — 유지' }

# ── 2. Git Bash 실행 경로 ───────────────────────────────
if (Test-Path $WtFragmentDir) { Remove-Item -LiteralPath $WtFragmentDir -Recurse -Force; Info "Windows Terminal 'Git Bash' 프로필 제거" }
if (Test-Path $StartMenuLnk) { Remove-Item -LiteralPath $StartMenuLnk -Force; Info "시작 메뉴 바로가기 제거: $StartMenuLnk" }

# ── 3. 사용자 PATH 에서 추가한 항목 제거 ─────────────────
$pathRec = Join-Path $BackupDir 'gitbash-path-added.txt'
if (Test-Path $pathRec) {
  $added = @(Get-Content -LiteralPath $pathRec | Where-Object { $_ })
  $envKey = Get-Item -Path 'HKCU:\Environment'
  $cur = $envKey.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
  if ($cur) {
    $parts = @($cur -split ';' | Where-Object { $_ })
    $kept = @($parts | Where-Object { $added -notcontains $_ })
    if ($kept.Count -ne $parts.Count) {
      Set-ItemProperty -Path 'HKCU:\Environment' -Name Path -Value ($kept -join ';') -Type $envKey.GetValueKind('Path')
      [Environment]::SetEnvironmentVariable('DOTFILES_GITBASH_REFRESH', $null, 'User')
      Info "사용자 PATH 에서 제거: $($added -join ', ')"
    }
  }
}

# ── 4. Git 제거 (-Purge, 이 스크립트가 설치한 것만) ─────
$gitRec = Join-Path $BackupDir 'gitbash-git-installed.txt'
$gitRemoved = $true
if ($Purge -and (Test-Path $gitRec)) {
  $rec = @{}
  foreach ($line in Get-Content -LiteralPath $gitRec) { if ($line -match '^(\w+)=(.*)$') { $rec[$Matches[1]] = $Matches[2] } }
  if (-not $rec.ContainsKey('path') -or -not $rec['path']) {
    Warn "$gitRec 에 경로가 없음 — Git 제거 건너뜀"; $gitRemoved = $false
  } elseif (-not (Test-Path $rec['path'])) {
    Info "Git 이 이미 없음: $($rec['path'])"
  } elseif ($rec['mode'] -eq 'installer') {
    $unins = Join-Path $rec['path'] 'unins000.exe'
    if (Test-Path $unins) {
      Info "Git 제거 중: $($rec['path'])"
      $p = Start-Process -FilePath $unins -ArgumentList @('/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES') -Wait -PassThru
      if ($p.ExitCode -ne 0) { Warn "제거 프로그램 종료 코드 $($p.ExitCode) — 설정 → 앱에서 Git 을 직접 제거"; $gitRemoved = $false }
    } else {
      Warn "제거 프로그램 없음: $unins — 설정 → 앱에서 Git 을 직접 제거"; $gitRemoved = $false
    }
  } elseif ($rec['mode'] -eq 'portable') {
    # 기록된 경로가 실제 PortableGit 인지(git-bash.exe 존재) 확인하고 지운다 — 엉뚱한 디렉터리를 지우지 않게
    if (Test-Path (Join-Path $rec['path'] 'git-bash.exe')) {
      Remove-Item -LiteralPath $rec['path'] -Recurse -Force
      Info "PortableGit 삭제: $($rec['path'])"
    } else {
      Warn "$($rec['path']) 에 git-bash.exe 가 없어 PortableGit 으로 보이지 않음 — 직접 확인 후 삭제"; $gitRemoved = $false
    }
  }
} elseif (Test-Path $gitRec) {
  Info 'Git 은 유지 (제거하려면 -Purge)'
}

# ── 5. 기록 정리 ────────────────────────────────────────
if ($KeepBackup) {
  Info "기록 유지: $BackupDir\gitbash-*"
} elseif (Test-Path $BackupDir) {
  # Git 을 남겨 두면(-Purge 없음·제거 실패) 나중에 -Purge 로 치울 수 있도록 설치 기록은 지우지 않는다
  Get-ChildItem -LiteralPath $BackupDir -Filter 'gitbash-*' -File | Where-Object {
    $_.Name -ne 'gitbash-git-installed.txt' -or ($Purge -and $gitRemoved)
  } | Remove-Item -Force
  # 비어 있으면 backup, dotfiles, .config 순으로 제거 (다른 파일이 있으면 그 단계에서 멈춘다)
  foreach ($d in $BackupDir, (Split-Path -Parent $BackupDir), (Join-Path $HomeDir '.config')) {
    if ((Test-Path $d) -and -not (Get-ChildItem -Force -LiteralPath $d | Select-Object -First 1)) { Remove-Item -LiteralPath $d -Force } else { break }
  }
}
Info '완료'
