#!/bin/sh
# Dev pilot: every gold set x methods x models into one results database. Resumable: rerun
# the same command and only missing or failed rows are attempted again.
#   RESULTS_DB=results-r3.duckdb scripts/pilot.sh nim-nemotron-ultra oc-gemma4-31b
set -u
models=""
for m in "$@"; do models="$models --model $m"; done
for set in gold_num gold_calc gold_trick; do
  uv run --no-sync loupe eval run "$set" --split dev --limit 24 \
    --arm b0 --arm rag --arm react --arm plan_execute --arm router --arm self_refine \
    --arm loupe --arm loupe-generic-tools \
    $models --judge ministral-14b
done
echo ALLDONE
