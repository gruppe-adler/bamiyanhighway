#!/bin/bash
# W2_queue.sh <key> [steps]   steps: b=build c=check r=report p=preview e=export (default bcrpe), u=uv check of the exported fbx.  One Blender job at a time, run it in the background.
# Env: W2_SCRATCH (blends + logs), default = ./_scratch next to this script.  Output: previews -> Docs/blender/caves/previews, FBX -> Assets/Tunnels/Cave
KEY=$1; STEPS=${2:-bcrpe}
HERE="$(cd "$(dirname "$0")" && pwd -W)"
ADDON="$(cd "$HERE/../../../.." && pwd -W)"
BL="C:/Program Files/Blender Foundation/Blender 4.5/blender.exe"
SC="${W2_SCRATCH:-$HERE/_scratch}"; mkdir -p "$SC" "$ADDON/Docs/blender/caves/previews" "$HERE/results"
export CAVE_OUT="$SC" W2_ASSET="$KEY" CAVE_RENDER=0 W2_PREV="$ADDON/Docs/blender/caves/previews" W2_PREV_OUT="$ADDON/Docs/blender/caves/previews"
NAME=$(python -I -c "import sys;sys.path.insert(0,r'$HERE');import W2_assets as A;print(A.build('$KEY')[0].name)")
BLEND="$SC/W2_${NAME}_v5.blend"
cd "$ADDON"
[[ $STEPS == *b* ]] && "$BL" --factory-startup -b --python "$HERE/W2_v5.py" > "$SC/W2_log_$KEY.txt" 2>&1
[[ $STEPS == *c* ]] && "$BL" --factory-startup -b "$BLEND" --python "$HERE/W2_check.py" > "$SC/W2_checklog_$KEY.txt" 2>&1
[[ $STEPS == *r* ]] && "$BL" --factory-startup -b "$BLEND" --python "$HERE/W2_report.py" > "$SC/W2_replog_$KEY.txt" 2>&1
[[ $STEPS == *p* ]] && "$BL" --factory-startup -b "$BLEND" --python "$HERE/W2_preview.py" > "$SC/W2_prevlog_$KEY.txt" 2>&1
if [[ $STEPS == *e* ]]; then
  CAVE_LOD_MIN=100000000 CAVE_ASSETS="$ADDON/Assets/Tunnels/Cave" CAVE_MASK_RES="${W2_MASK_RES:-2048}" "$BL" --factory-startup -b "$BLEND" --python "$HERE/W2_export.py" > "$SC/W2_exportlog_$KEY.txt" 2>&1
fi
if [[ $STEPS == *u* ]]; then
  "$BL" -b --factory-startup --python "$HERE/W2_uvcheck.py" -- "$ADDON/Assets/Tunnels/Cave/$NAME.fbx" "$HERE/results/W2_uv_$NAME.json" ${W2_MASK_RES:-2048} > "$SC/W2_uvlog_$KEY.txt" 2>&1
fi
cp -f "$SC/W2_stats_$NAME.json" "$SC/W2_check_$NAME.json" "$SC/W2_report_$NAME.json" "$HERE/results/" 2>/dev/null
echo "QUEUE DONE $KEY $NAME"
