# Operations

Run-level forensics for the archive workflows. The day-to-day description of where archives live stays in [`DATA_SOURCES.md`](DATA_SOURCES.md); this file holds the observed schedule history and residual-risk notes moved verbatim out of the README on 2026-11-13.

## Daily forecast archive — schedule forensics

**Schedule status as of 2026-11-12: proven, but every run that day started hours late.** The first `event=schedule` run completed on 2026-11-12 15:37 UTC ([run 43249798026](https://github.com/Akunimal/prisma-climate/actions/runs/43249798026), `event=schedule`, conclusion `success`, headSha `1e82b23`); two more schedule runs started that day at 19:52 UTC ([run 43294532842](https://github.com/Akunimal/prisma-climate/actions/runs/43294532842)) and 23:44 UTC ([run 43331372851](https://github.com/Akunimal/prisma-climate/actions/runs/43331372851)), both `success`. GitHub does not expose which cron produced which run, so the mapping is **inferred** (usual reading: the 12:17 slot ran ~3h20m late at 15:37 and the 18:31 slot ~1h21m late at 19:52, leaving the 06:47 slot to have run at 23:44, ~16h57m late; `docs/DATA_SOURCES.md` lists every admitted reading) — under **every** one-to-one reading the closest any run came to its slot was ~1h21m, so no run that day was on time. The 06:47 slot had produced no run by that morning, so the 2026-11-12 issue date was archived by a manual `workflow_dispatch` rescue at 08:31 UTC ([run 43183607191](https://github.com/Akunimal/prisma-climate/actions/runs/43183607191)); no Release fallback was used for it. All three scheduled runs were data no-ops for the archive (the canonical file already existed; they only left the ingest status heartbeat commits). The archive path itself is proven: both issue dates to date were uploaded successfully (2026-11-11 via backfill, 2026-11-12 via dispatch), and a later same-day run is a tested no-op that never overwrites the canonical file.

**Residual risk, stated plainly.** GitHub's schedule is best-effort: a slot can be delayed by hours or dropped, and a UTC day whose slots all fail to produce a successful run is **lost verification data** — nothing self-heals. `scripts/archive_watchdog.py` (run by the workflow, visibility only) records missing days under `archive_watchdog` in [`results/ingest_status.json`](../results/ingest_status.json); it never repairs anything, and it reads the archive through a Hugging Face repository listing that can be cache-prone — a reported missing day may be a false positive and should be verified against the dataset before acting. Following the delays observed on 2026-11-12, the slots were redesigned on 2026-11-13 to **06:47, 09:47, 12:17, 14:43 and 18:31 UTC**: the original 06:47 attempt kept for spread (for dropped rather than delayed slots, more spread-out attempts hedge better, and 06:47 plus a multi-hour delay still lands inside the same UTC day), three attempts inside 09:00–15:00 UTC, where a multi-hour delay still lands inside the same UTC day (the issue date is the fetch date), plus 18:31 as the last chance of the day.

## Owner-side daily dispatch (registered 2026-11-14 UTC)

**What it is.** [`scripts/local_dispatch.ps1`](../scripts/local_dispatch.ps1) runs `gh workflow run ingest.yml` and `gh workflow run observations.yml` on branch `main` using the owner's existing `gh` login (no token in the script, no stored password, nothing Hugging Face related), and appends a timestamped line per dispatch — or per error — to `%LOCALAPPDATA%\prisma-climate\local_dispatch.log`, a log file **outside the repository**. Both workflows are idempotent: when the day is already archived the run is a data no-op (an ingest run may still leave its status heartbeat commit).

**Scheduled task.** The script is registered in Windows Task Scheduler as **`PRISMA daily dispatch`**: daily at **10:00 America/Argentina/Buenos_Aires** (the machine is on `Argentina Standard Time`, UTC−3), principal = the current user with logon type Interactive (**no stored password**, `RunLevel=Limited`), and **"run as soon as possible after a scheduled start is missed"** enabled (`StartWhenAvailable=True`, registered between 2026-11-14T00:18:53Z and 00:20:40Z; next run observed as 2026-11-14 10:00 local). Its action is `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\WORK\Climate Prediction\scripts\local_dispatch.ps1"`.

**What its runs look like.** Every run it triggers appears in GitHub Actions with **`event=workflow_dispatch`**, never as `schedule`; the GitHub cron history is therefore not mixed with these owner-side runs. The GitHub crons stay exactly as they are — this is a second, owner-side attempt for a workflow day GitHub's scheduler may have dropped, not a replacement for it.

**Limits, stated plainly.** It only works while the owner's PC is **on and logged in** (Interactive logon): a run missed while the PC is off starts as soon as possible after the PC is next available, not in the cloud. It holds no secrets of its own — `gh` supplies the token — and it never touches Hugging Face credentials.

**How to disable / enable / remove** (PowerShell):

```powershell
Disable-ScheduledTask -TaskName 'PRISMA daily dispatch'    # keep, stop firing
Enable-ScheduledTask  -TaskName 'PRISMA daily dispatch'    # re-enable
Unregister-ScheduledTask -TaskName 'PRISMA daily dispatch' -Confirm:$false   # remove
```

Disabling the task does not touch the script or the log; the log (`%LOCALAPPDATA%\prisma-climate\local_dispatch.log`) records every dispatch with a UTC timestamp.

**Test execution (2026-11-14, owner-authorized, exactly one manual run of the script).** Both dispatches queued at 2026-11-14T00:16:33Z / 00:16:36Z: ingest [run 43533076811](https://github.com/Akunimal/prisma-climate/actions/runs/43533076811) concluded **success**; observations [run 43533080727](https://github.com/Akunimal/prisma-climate/actions/runs/43533080727) concluded **failure** — both daily payloads (datohorario, observaciones) came back carrying no parseable `FECHA` value at 00:16Z (SMN-side content at fetch time), the workflow's failure path reported "A capture failed; that payload is lost for the day (no backfill)", and the gap-visibility step ran successfully for the first time. The `regtemp` capture step in that run concluded success.

