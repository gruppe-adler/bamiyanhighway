#!/bin/bash
SP="$1"; B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
SRC="D:/gronom/Auftraege/2016/GruppeAdler/Modding/bamiyan_highway/blender/cliffs"
CL="c:/Users/nomisum/Documents/my games/ArmaReforgerWorkbench/addons/Shashpul/Prefabs/Rocks/Cliffs"
cd "$SP/work"
while read src A SIZE; do
  echo "=== $A"
  "$B" -b --factory-startup --disable-autoexec "$SRC/$src" --python-exit-code 1 -P "$SP/s/enf_a_lod0.py" -- enf/${A}_work.blend $SIZE > logs_a_$A.txt 2>&1
  grep -E "^A_DESHELL|^A_DEC|^A_CLOSE|^A_MESH|^A_WROTE" logs_a_$A.txt | cut -c1-250
  grep -q "^A_WROTE" logs_a_$A.txt || { echo "$A STAGE A FAILED"; continue; }
  "$B" -b --factory-startup --disable-autoexec enf/${A}_work.blend --python-exit-code 1 -P "$SP/s/enf_u_uv.py" -- enf/${A}_work_v3.blend $SIZE > logs_u_$A.txt 2>&1
  grep -E "^U_UV" logs_u_$A.txt | cut -c1-120; grep -q "^U_WROTE" logs_u_$A.txt || { echo "$A UV FAILED"; continue; }
  CYCLES_DEV=HIP "$B" -b --factory-startup --disable-autoexec enf/${A}_work_v3.blend --python-exit-code 1 -P "$SP/s/enf_m_mask.py" -- enf/${A}_mask_v3.npy "$SP/tex" 4096 > logs_m_$A.txt 2>&1
  grep -E "^M_BAKED|^M_NMO" logs_m_$A.txt | cut -c1-250; grep -q "^M_DONE" logs_m_$A.txt || { echo "$A MASK FAILED"; continue; }
  "$B" -b --factory-startup --disable-autoexec enf/${A}_work_v3.blend --python-exit-code 1 -P "$SP/s/enf_c3_export.py" -- enf/${A}_mask_v3.npy "$CL/$A" $A $SIZE > logs_c_$A.txt 2>&1
  grep -E "^C_SCALE|^C_TILING|^C_COLLIDER|^C_OCC|^C_DONE" logs_c_$A.txt | cut -c1-300
done <<LIST
Meshy_AI_Eroded_Redstone_Monol_1024181237_generate.blend Cliff_ErodedRedstoneMonolith 20.6
LIST
echo ALL_DONE
