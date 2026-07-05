# Checklist: Runtime Migration Closeout

Status: example
Type: checklist
Updated: 2026-07-05
Next Action: none
Parent: work/wp/completed/wp-runtime-migration.md

## Goal

Close a runtime migration only after proving the new surface is healthy, the old surface is not still doing the same work, and rollback/reference paths are recorded.

## Checklist

- [ ] Confirm new service, scheduler, worker, or manual command is running or succeeds.
- [ ] Confirm internal status reports the expected state.
- [ ] Confirm external status or health endpoint reports the expected state.
- [ ] Confirm old timer, service, cron job, or scheduler path is disabled, inactive, or intentionally retained.
- [ ] Confirm duplicate scheduling cannot happen.
- [ ] Record rollback commands or reference surfaces.
- [ ] Record ignored local config files that materially affect runtime behavior.
- [ ] Update README/docs with current operating truth.
- [ ] Move completed delivery artifacts to history or mark them complete.
- [ ] Run stale-path check after moving artifacts.

## Runtime Closeout

- [ ] New runtime surface is up or the intended manual command succeeds.
- [ ] Published/status surface reports the expected state.
- [ ] Old runtime surface is disabled, inactive, or explicitly retained.
- [ ] Rollback/reference surfaces are recorded.
- [ ] Ignored local config changed during the work is listed with matching tracked examples or docs.

## Verification

```bash
docker compose ps service-name
curl -fsS http://127.0.0.1:PORT/health.json
systemctl is-enabled old-service.timer || true
systemctl is-active old-service.timer || true
python3 tool_shed/scripts/check_stale_paths.py --workspace .
```
