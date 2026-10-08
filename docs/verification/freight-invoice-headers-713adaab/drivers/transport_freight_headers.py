from pathlib import Path, PurePosixPath
import base64,datetime,hashlib,json,subprocess,uuid,zipfile,sys

ROOT=Path("/dev/shm/chatgpt-freight-invoice-headers-713adaab")
PACKET=ROOT/"evidence/windows"
HOST="minec@100.115.131.125"
SSH_OPTIONS=["-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=10",
             "-o","LogLevel=ERROR","-i","/home/jacob/.ssh/id_ed25519"]

def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def call(label,command,timeout=120):
    started=now()
    with (PACKET/(label+".stdout.txt")).open("xb") as out,(PACKET/(label+".stderr.txt")).open("xb") as err:
        result=subprocess.run(command,stdout=out,stderr=err,timeout=timeout)
    raw=(PACKET/(label+".stdout.txt")).read_bytes()
    record={"argv":command,"returncode":result.returncode,"started_utc":started,"finished_utc":now(),
            "stdout_sha256":digest(raw),"stderr_sha256":digest((PACKET/(label+".stderr.txt")).read_bytes())}
    (PACKET/(label+".transport.json")).write_text(json.dumps(record,indent=2)+"\n")
    return record,raw
def powershell(label,source,timeout=120):
    (PACKET/(label+".ps1")).write_text(source,encoding="utf-8")
    return call(label,["ssh",*SSH_OPTIONS,HOST,"powershell.exe","-NoProfile","-NonInteractive",
                       "-EncodedCommand",base64.b64encode(source.encode("utf-16le")).decode()],timeout)

PACKET.mkdir()
namespace="hamon-freight-headers-713adaab-"+uuid.uuid4().hex
(PACKET/"transport-started.json").write_text(json.dumps({"started_utc":now(),"namespace":namespace},indent=2)+"\n")
paths=subprocess.check_output(["git","-C",str(ROOT/"source"),"ls-files"],text=True).splitlines()
paths.append("freight_packets/tests/test_invoice_header_consistency.py")
manifest={"upstream_source_commit":"9e931fa9f42033bf2368f7149684fb5631345715","files":[]}
for path in sorted(paths):
    raw=(ROOT/"source"/path).read_bytes()
    manifest["files"].append({"path":path,"bytes":len(raw),"sha256":digest(raw),
                             "git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()})
(PACKET/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
bundle=PACKET/"source-bundle.zip"
with zipfile.ZipFile(bundle,"x",compression=zipfile.ZIP_DEFLATED) as z:
    for row in manifest["files"]:
        z.write(ROOT/"source"/row["path"],"source/"+row["path"])
    for case in sorted((ROOT/"evidence/baseline").iterdir()):
        data=case/"data"
        if data.is_dir():
            for path in sorted(data.rglob("*")):
                if path.is_file():z.write(path,"input/"+case.name+"/data/"+path.relative_to(data).as_posix())
    z.write(PACKET/"source-manifest.json","source-manifest.json")
    z.write(ROOT/"receive_freight_headers.py","receive_freight_headers.py")
bundle_sha=digest(bundle.read_bytes())
setup=r'''$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$qaRoot=Join-Path ([IO.Path]::GetTempPath()) '__NAMESPACE__'
if (Test-Path -LiteralPath $qaRoot) { throw 'Receiving namespace already exists' }
New-Item -ItemType Directory -Path $qaRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $qaRoot 'evidence') | Out-Null
$qaVolume=Get-Volume -DriveLetter C
$qaRecord=@{ namespace=$qaRoot; host=$env:COMPUTERNAME; filesystem=$qaVolume.FileSystem; available_bytes=$qaVolume.SizeRemaining; total_bytes=$qaVolume.Size; observed_utc=[DateTime]::UtcNow.ToString('o') }
[IO.File]::WriteAllText((Join-Path $qaRoot 'evidence\windows-filesystem.json'),($qaRecord|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$qaRecord | ConvertTo-Json -Depth 6
'''.replace("__NAMESPACE__",namespace)
setup_record,setup_raw=powershell("setup",setup)
if setup_record["returncode"]:raise RuntimeError("setup refused; no upload or execution")
windows=json.loads(setup_raw.decode("utf-8-sig"))
upload,_=call("source-upload",["scp",*SSH_OPTIONS,str(bundle),HOST+":AppData/Local/Temp/"+namespace+"/source-bundle.zip"])
if upload["returncode"]:raise RuntimeError("upload refused; no receiving execution")
execute=r'''$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$qaRoot=Join-Path ([IO.Path]::GetTempPath()) '__NAMESPACE__'
$qaBundle=Join-Path $qaRoot 'source-bundle.zip'
if ((Get-FileHash -LiteralPath $qaBundle -Algorithm SHA256).Hash.ToLowerInvariant() -ne '__BUNDLE_SHA__') { throw 'Source archive hash mismatch' }
Expand-Archive -LiteralPath $qaBundle -DestinationPath $qaRoot
$qaEvidence=Join-Path $qaRoot 'evidence'
$qaDriver=Join-Path $qaRoot 'receive_freight_headers.py'
$qaArgs='-3.11 -I -S -B -X utf8 "'+$qaDriver+'" --qa-root "'+$qaRoot+'"'
$qaStarted=[DateTime]::UtcNow.ToString('o')
$qaProcess=Start-Process -FilePath 'C:\Windows\py.exe' -ArgumentList $qaArgs -WorkingDirectory $qaRoot -Wait -PassThru -RedirectStandardOutput (Join-Path $qaEvidence 'driver.stdout.txt') -RedirectStandardError (Join-Path $qaEvidence 'driver.stderr.txt')
$qaRecord=@{ launcher='C:\Windows\py.exe'; arguments=$qaArgs; started_utc=$qaStarted; finished_utc=[DateTime]::UtcNow.ToString('o'); inner_qualification_exit_code=$qaProcess.ExitCode; source_bundle_sha256='__BUNDLE_SHA__'; driver_sha256=(Get-FileHash -LiteralPath $qaDriver -Algorithm SHA256).Hash.ToLowerInvariant() }
[IO.File]::WriteAllText((Join-Path $qaEvidence 'native-process.json'),($qaRecord|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$qaArchive=Join-Path $qaRoot 'receiving-evidence.zip'
$qaItems=@($qaEvidence)
if (Test-Path -LiteralPath (Join-Path $qaRoot 'reports')) { $qaItems += (Join-Path $qaRoot 'reports') }
Compress-Archive -LiteralPath $qaItems -DestinationPath $qaArchive -CompressionLevel Optimal
@{ namespace=$qaRoot; qualification_exit_code=$qaProcess.ExitCode; archive_sha256=(Get-FileHash -LiteralPath $qaArchive -Algorithm SHA256).Hash.ToLowerInvariant(); archive_bytes=(Get-Item -LiteralPath $qaArchive).Length } | ConvertTo-Json -Depth 6
exit $qaProcess.ExitCode
'''.replace("__NAMESPACE__",namespace).replace("__BUNDLE_SHA__",bundle_sha)
execution,execution_raw=powershell("receiving",execute,180)
summary=json.loads(execution_raw.decode("utf-8-sig"))
archive=PACKET/"receiving-evidence.zip"
download,_=call("evidence-download",["scp",*SSH_OPTIONS,HOST+":AppData/Local/Temp/"+namespace+"/receiving-evidence.zip",str(archive)])
if download["returncode"]:raise RuntimeError("download refused; native result retained")
if digest(archive.read_bytes())!=summary["archive_sha256"] or archive.stat().st_size!=summary["archive_bytes"]:
    raise RuntimeError("receiving archive identity mismatch")
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        path=PurePosixPath(member.filename.replace("\\","/"))
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in ("evidence","reports"):
            raise RuntimeError("unexpected archive member")
        dest=PACKET/"native"/path
        if member.is_dir():dest.mkdir(parents=True,exist_ok=True)
        else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
report=json.loads((PACKET/"native/evidence/receiving-report.json").read_text(encoding="utf-8"))
result={"namespace":windows["namespace"],"native_host":windows["host"],"filesystem":windows["filesystem"],
        "source_bundle_bytes":bundle.stat().st_size,"source_bundle_sha256":bundle_sha,
        "archive_bytes":archive.stat().st_size,"archive_sha256":summary["archive_sha256"],
        "setup_returncode":setup_record["returncode"],"upload_returncode":upload["returncode"],
        "execution_transport_returncode":execution["returncode"],"download_returncode":download["returncode"],
        "qualification_exit_code":report["qualification_exit_code"],"native_process_exits":[r["returncode"] for r in report["cases"]],
        "report_sha256":digest((PACKET/"native/evidence/receiving-report.json").read_bytes()),
        "source_sha256":report["source_sha256"],"test_sha256":report["test_sha256"],
        "source_unchanged":report.get("source_unchanged"),"inputs_unchanged":report.get("input_unchanged"),
        "all_six_refusals_preserve_reports":report.get("all_six_refusals_preserve_reports"),"finished_utc":now()}
(PACKET/"transport-summary.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
raise SystemExit(report["qualification_exit_code"])
