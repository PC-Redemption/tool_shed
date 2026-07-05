# Checklist: Root Docs Cleanup

Status: example
Type: checklist
Updated: 2026-07-05
Next Action: none

## Goal

Move long-form docs out of the project root while preserving links and build behavior.

## Checklist

- [ ] Inventory root files
- [ ] Classify keep, move, delete
- [ ] Move approved docs
- [ ] Add docs index
- [ ] Update links
- [ ] Run tests
- [ ] Scan for stale links

## Verification

```bash
find . -maxdepth 1 -type f -printf '%f\n' | sort
make test
rg -n 'OLD_DOC_NAME.md' .
```

