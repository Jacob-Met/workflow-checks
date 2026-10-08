$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$qaRoot=Join-Path ([IO.Path]::GetTempPath()) 'hamon-freight-headers-713adaab-fb3a2ca166494553ba685bb70cf11acb'
$qaBundle=Join-Path $qaRoot 'source-bundle.zip'
if ((Get-FileHash -LiteralPath $qaBundle -Algorithm SHA256).Hash.ToLowerInvariant() -ne '4332367b24e1fda29ae7955a3439a12cf6b880d526ee59b7d4b13829526260f1') { throw 'Source archive hash mismatch' }
Expand-Archive -LiteralPath $qaBundle -DestinationPath $qaRoot
$qaEvidence=Join-Path $qaRoot 'evidence'
$qaDriver=Join-Path $qaRoot 'receive_freight_headers.py'
$qaArgs='-3.11 -I -S -B -X utf8 "'+$qaDriver+'" --qa-root "'+$qaRoot+'"'
$qaStarted=[DateTime]::UtcNow.ToString('o')
$qaProcess=Start-Process -FilePath 'C:\Windows\py.exe' -ArgumentList $qaArgs -WorkingDirectory $qaRoot -Wait -PassThru -RedirectStandardOutput (Join-Path $qaEvidence 'driver.stdout.txt') -RedirectStandardError (Join-Path $qaEvidence 'driver.stderr.txt')
$qaRecord=@{ launcher='C:\Windows\py.exe'; arguments=$qaArgs; started_utc=$qaStarted; finished_utc=[DateTime]::UtcNow.ToString('o'); inner_qualification_exit_code=$qaProcess.ExitCode; source_bundle_sha256='4332367b24e1fda29ae7955a3439a12cf6b880d526ee59b7d4b13829526260f1'; driver_sha256=(Get-FileHash -LiteralPath $qaDriver -Algorithm SHA256).Hash.ToLowerInvariant() }
[IO.File]::WriteAllText((Join-Path $qaEvidence 'native-process.json'),($qaRecord|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$qaArchive=Join-Path $qaRoot 'receiving-evidence.zip'
$qaItems=@($qaEvidence)
if (Test-Path -LiteralPath (Join-Path $qaRoot 'reports')) { $qaItems += (Join-Path $qaRoot 'reports') }
Compress-Archive -LiteralPath $qaItems -DestinationPath $qaArchive -CompressionLevel Optimal
@{ namespace=$qaRoot; qualification_exit_code=$qaProcess.ExitCode; archive_sha256=(Get-FileHash -LiteralPath $qaArchive -Algorithm SHA256).Hash.ToLowerInvariant(); archive_bytes=(Get-Item -LiteralPath $qaArchive).Length } | ConvertTo-Json -Depth 6
exit $qaProcess.ExitCode
