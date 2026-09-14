param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectDir
)

$ErrorActionPreference = 'Stop'
$ProjectDir = [System.IO.Path]::GetFullPath($ProjectDir)
$ToolsDir = Join-Path $ProjectDir '.tools'
$ResultFile = Join-Path $ToolsDir 'java_home.txt'
New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

function Get-JavaMajor([string]$Home) {
    if ([string]::IsNullOrWhiteSpace($Home)) { return $null }
    $java = Join-Path $Home 'bin\java.exe'
    if (-not (Test-Path $java)) { return $null }
    try {
        $line = (& $java -version 2>&1 | Select-Object -First 1).ToString()
        if ($line -match 'version\s+"([0-9]+)') { return [int]$Matches[1] }
    } catch {}
    return $null
}

function Add-Candidate([System.Collections.Generic.List[string]]$List, [string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    try { $full = [System.IO.Path]::GetFullPath($Path) } catch { return }
    if (-not $List.Contains($full)) { $List.Add($full) }
}

$candidates = New-Object 'System.Collections.Generic.List[string]'
Add-Candidate $candidates (Join-Path $env:ProgramFiles 'Android\Android Studio\jbr')
if ($env:LOCALAPPDATA) {
    Add-Candidate $candidates (Join-Path $env:LOCALAPPDATA 'Programs\Android Studio\jbr')
    Add-Candidate $candidates (Join-Path $env:LOCALAPPDATA 'Android\Android Studio\jbr')
}
Add-Candidate $candidates $env:JAVA_HOME
Add-Candidate $candidates (Join-Path $ToolsDir 'jdk-21')

$roots = @(
    (Join-Path $env:ProgramFiles 'Eclipse Adoptium'),
    (Join-Path $env:ProgramFiles 'Microsoft'),
    (Join-Path $env:ProgramFiles 'Java')
)
foreach ($root in $roots) {
    if (Test-Path $root) {
        Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'jdk-21*' -or $_.Name -like 'jdk-17*' } |
            ForEach-Object { Add-Candidate $candidates $_.FullName }
    }
}

$chosen = $null
foreach ($candidate in $candidates) {
    $major = Get-JavaMajor $candidate
    if ($major -eq 17 -or $major -eq 21) {
        $chosen = $candidate
        Write-Host "Pouziji JDK ${major}: $chosen"
        break
    }
    elseif ($major) {
        Write-Host "Preskakuji nekompatibilni JDK ${major}: $candidate"
    }
}

if (-not $chosen) {
    $dest = Join-Path $ToolsDir 'jdk-21'
    $zip = Join-Path $ToolsDir 'temurin21.zip'
    $tmp = Join-Path $ToolsDir 'temurin21_tmp'
    Write-Host 'Kompatibilni JDK 17/21 nebylo nalezeno. Stahuji prenosne Eclipse Temurin JDK 21...'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    if (Test-Path $zip) { Remove-Item $zip -Force }
    $url = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse'
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip
    Expand-Archive -Force -Path $zip -DestinationPath $tmp
    $root = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (-not $root) { throw 'Stazeny archiv JDK nema ocekavanou strukturu.' }
    Move-Item -Path $root.FullName -Destination $dest
    Remove-Item $zip -Force
    Remove-Item $tmp -Recurse -Force
    $major = Get-JavaMajor $dest
    if ($major -ne 21) { throw "Stazene JDK ma neocekavanou verzi: $major" }
    $chosen = $dest
    Write-Host "JDK 21 pripraveno: $chosen"
}

Set-Content -Path $ResultFile -Value $chosen -Encoding ASCII -NoNewline
