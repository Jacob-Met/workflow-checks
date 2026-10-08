$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$qaRoot=Join-Path ([IO.Path]::GetTempPath()) 'hamon-freight-headers-713adaab-fb3a2ca166494553ba685bb70cf11acb'
if (Test-Path -LiteralPath $qaRoot) { throw 'Receiving namespace already exists' }
New-Item -ItemType Directory -Path $qaRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $qaRoot 'evidence') | Out-Null
$qaVolume=Get-Volume -DriveLetter C
$qaRecord=@{ namespace=$qaRoot; host=$env:COMPUTERNAME; filesystem=$qaVolume.FileSystem; available_bytes=$qaVolume.SizeRemaining; total_bytes=$qaVolume.Size; observed_utc=[DateTime]::UtcNow.ToString('o') }
[IO.File]::WriteAllText((Join-Path $qaRoot 'evidence\windows-filesystem.json'),($qaRecord|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$qaRecord | ConvertTo-Json -Depth 6
