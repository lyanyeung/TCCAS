# TCCAS — IRIDIS6 archive and recovery

Reusable workflows for archiving historical TCCAS / D&B experiments from the University of Southampton IRIDIS6 to Research Filestore and restoring them for future model runs.

**This is a PUBLIC, code-only repository.** Do not commit original TCCAS source from third parties, flux-tower data, forcing, observation files, NetCDF outputs, Research Filestore archives, manifests, credentials, or copied HPC case directories. The Research Filestore keeps the private data, not GitHub.

## Known IRIDIS6 state (20 October 2026)

- Confirmed source: `/home/ly3n24/DB` — about 240 MB, 405 regular files, 24 symlinks.
- The inspected known Scratch paths did not contain a TCCAS directory. There may be others under different names; audit separately.
- Research Filestore: `/research/xclimatetbm/ly3n24` (autofs-backed NFS).
- Archive destination: `/research/xclimatetbm/ly3n24/TCCAS_Archive/`.
- **Moving the Home DB directory does not release Scratch inodes**. CLM-FATES Scratch cleanup is a separate task.

## Download on IRIDIS6

```bash
cd "$HOME"
git clone https://github.com/lyanyeung/TCCAS.git TCCAS-workflows
cd TCCAS-workflows
python3 scripts/archive_tccas.py inspect
```

The inspect mode performs no writes and reports selected sources, symbolic links and any additional Scratch candidates. Review the results before migration.

## Move data to Research Filestore

```bash
# First copy and SHA-256 verify, retaining the source:
bash scripts/run_once.sh copy

# If satisfied that the directory is unused, attempt a verified move:
TCCAS_CONFIRM_DELETE=YES bash scripts/run_once.sh move
```

**The \`move\` command requires \`TCCAS_CONFIRM_DELETE=YES\` and should only be run after checking that no workflows depend on the source path.** If uncertain, use \`copy\` only.\n\nThe archive is written **directly to Research Filestore** as `*.tar.gz`, `*.manifest.json`, and a SHA-256 receipt. No temporary full-size archive is made on Scratch. The `move` mode deletes a selected original only after archive verification, unchanged-source checks, and Slurm/job/symlink safety gates. It will refuse deletion if it detects links to outside the source tree or active relevant jobs. No CLM-FATES case directories or CIME restarts are targeted. If the archive already exists, it is re-verified instead of overwritten. Check final output and `myfiles`; do not treat copy alone as Scratch cleanup.

To include another *confirmed* TCCAS installation, use e.g. `python3 scripts/archive_tccas.py inspect --source /absolute/path`. Unknown deeper Scratch candidates are displayed but **not automatically removed**.

**Caution:** An automated safety check cannot prove no independent script or model references `/home/ly3n24/DB`. Confirm those external dependencies before using `move`. Running jobs are not modified or canceled.

## Restore and rerun later

```bash
# First choose the actual archive and inspect its manifest:
find /research/xclimatetbm/ly3n24/TCCAS_Archive -name '*.manifest.json'

# Restore a verified archive (will refuse to overwrite an existing directory):
python3 scripts/restore_tccas.py /research/xclimatetbm/ly3n24/TCCAS_Archive/home/home__ly3n24__DB.tar.gz

# After checking toolchain, domain configuration, and external linked inputs:
bash scripts/submit_tccas.sh FI-Sod --dry-run
bash scripts/submit_tccas.sh FI-Sod --submit
```

The restore tool validates the archived SHA-256 and member paths and extracts only to the original parent directory. Exact archive name depends on the resolved original path. Compilation and domain setup may need changes for current Fortran/NetCDF dependencies and original model configuration. The submit script is an **illustrative Slurm recipe** (`make runmodel.x` and `make xmodel DOMAIN=<site>`), not evidence that a future build has been tested.

## Files

- `scripts/archive_tccas.py`: discover, inspect, copy, cryptographically verify and selectively move TCCAS directories
- `scripts/run_once.sh`: run inventory + transfer on IRIDIS6; choose `copy` or `move`
- `scripts/restore_tccas.py`: safe verified extraction back into original directory
- `scripts/submit_tccas.sh`: dry-run or Slurm submission for an explicitly selected restored domain
- `.gitignore`: prevent accidentally committing data archives, model outputs and credentials

Original project provenance should be checked against the files included in each archive; GitHub stores this workflow only.