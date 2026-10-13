# Opening a saved review worksheet

The [review desk](review-desk.md) reads one explicitly selected worksheet. It
keeps the existing 8 MiB byte limit, complete native CSV validation, and snapshot
checks before downloads and source inspection.

## File admission

A worksheet must resolve to a regular file. Ordinary files and symlinks to
regular files retain their existing behavior. A directory, named pipe or
symlink to a named pipe is refused.

The early path check remains in place. The binary reader also opens with
`O_NONBLOCK` where that flag is available and checks the opened descriptor with
`fstat` before reading from that same handle. This prevents waiting for a pipe
writer if the selected path changes to a FIFO after the early metadata check.
The handle is closed on success and refusal. UTF-8/CSV interpretation still
belongs to the unchanged native worksheet validator.

An invalid worksheet at startup follows the existing CLI error path before the
listener starts. If the selected worksheet becomes unreadable while the desk
is running, its existing snapshot check returns HTTP 409 for the refused
download or inspection. The desk does not write the selected worksheet.
Restoring the originally selected bytes permits the existing retry behavior;
a different worksheet requires restarting with the intended file.

The change does not lock a pathname, make several source files an atomic
snapshot, or establish a general filesystem I/O deadline. Its additional
admission is for the descriptor actually being read and the named-pipe opening
case. Worksheet schema, annotations, source-evidence validation, download
contents, HTTP/session policy and payment eligibility retain their existing
implementations.

## Focused regression course

From `utility_watch/`:

```sh
python -B -m unittest discover -s tests -p test_review_desk_file_kinds.py -v
python -B -m pytest -q tests/test_review_desk.py tests/test_review_evidence.py
```

The eight new methods cover exact Unicode/CRLF bytes, regular symlinks, the
existing 8 MiB boundary, ordinary nonregular refusals, and two real file
replacements at Python's open audit event. Named-pipe cases run in bounded child
processes; a timeout kills and reaps the child. POSIX-only cases are skipped on
platforms without `os.mkfifo`.

The download course uses a fictional worksheet from the maintained native
fixture, an owned loopback listener and an actual HTTP request. It replaces the
selected file with a pipe immediately before the filesystem open, expects a
409 refusal, restores the original bytes, and retries the same edits. The
successful retry must return a native-valid complete CSV with the exact note,
while the selected worksheet remains unchanged. This is a command/HTTP
receiving check; it does not claim a new browser or real-client qualification.

[Issue 108](https://github.com/Jacob-Met/workflow-checks/issues/108) records the
source ownership, original-first receiving and reviewed integration.
