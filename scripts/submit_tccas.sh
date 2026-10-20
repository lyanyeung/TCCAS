#!/usr/bin/env bash
set -euo pipefail
DOMAIN="${1:?Usage: submit_tccas.sh FI-Sod --dry-run|--submit}"
MODE="${2:---dry-run}"
[[ "$DOMAIN" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Invalid domain" >&2; exit 2; }
[[ "$MODE" == "--dry-run" || "$MODE" == "--submit" ]] || { echo "Choose --dry-run or --submit" >&2; exit 2; }
ROOT="${TCCAS_ROOT:-$HOME/DB}"
[[ -f "$ROOT/Makefile" && -d "$ROOT/config" ]] || { echo "Missing TCCAS installation: $ROOT" >&2; exit 2; }
CPUS="${CPUS:-1}"; MEM="${MEM:-8G}"; WALLTIME="${WALLTIME:-04:00:00}"
[[ "$CPUS" =~ ^[1-9][0-9]*$ && "$MEM" =~ ^[1-9][0-9]*[GM]$ && "$WALLTIME" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]] || { echo "Invalid resources" >&2; exit 2; }
echo "TCCAS domain=$DOMAIN root=$ROOT CPU=$CPUS MEM=$MEM time=$WALLTIME"
echo 'Planned commands: make runmodel.x ; make xmodel DOMAIN=<domain>'
if [[ "$MODE" == "--dry-run" ]]; then echo "DRY RUN ONLY. Review domain, inputs and compiler."; exit 0; fi
command -v sbatch >/dev/null || { echo "sbatch unavailable" >&2; exit 2; }
sbatch --job-name="TCCAS_${DOMAIN}" --partition=batch --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" --mem="$MEM" --time="$WALLTIME" --chdir="$ROOT" --output="$ROOT/TCCAS_%j.out" --export="ALL,TCCAS_DOMAIN=$DOMAIN" <<'BATCH'
#!/usr/bin/env bash
set -euo pipefail
if [[ -d "$HOME/.conda/envs/ncl_env/lib" ]]; then
  export LD_LIBRARY_PATH="$HOME/.conda/envs/ncl_env/lib:${LD_LIBRARY_PATH:-}"
fi
if [[ -f config/mk.compile-gfortran ]]; then
  ln -sfn config/mk.compile-gfortran mk.compile
fi
make runmodel.x
make xmodel "DOMAIN=$TCCAS_DOMAIN"
BATCH
