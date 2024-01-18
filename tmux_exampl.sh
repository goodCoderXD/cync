SOURCE="/home/titan/Documents/NVIDIA/computelab/packages/stedge/stedge/state_managers/gpu_envvars.py"
TARGET="/computelab-python/packages/stedge/stedge/state_managers/gpu_envvars.py"
TMP_TARGET="/tmp/gpu_envvars.py"

for i in {94..100}; do
    sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@lego-cg1-qs-$i" sudo chmod g+w "$TARGET"
    sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" scp "$SOURCE" "svc-computelab@lego-cg1-qs-$i:$TMP_TARGET"
    sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@lego-cg1-qs-$i" sudo mv "$TMP_TARGET" "$TARGET"
    sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@lego-cg1-qs-$i" cat "$TARGET" | grep rusu
done

sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" scp "$SOURCE" "svc-computelab@ipp1-1062:$TMP_TARGET"
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@ipp1-1062" sudo mv "$TMP_TARGET" "$TARGET"
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@ipp1-1062" cat "$TARGET" | grep rusu

i=94
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@lego-cg1-qs-$i" sudo chmod g+w "$TARGET"
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" scp "$SOURCE" "svc-computelab@lego-cg1-qs-$i:$TMP_TARGET"
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh "svc-computelab@lego-cg1-qs-$i" sudo mv "$TMP_TARGET" "$TARGET"

sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh svc-computelab@lego-cg1-qs-97
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh svc-computelab@lego-cg1-qs-98
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh svc-computelab@lego-cg1-qs-99
sshpass -p "GYJZvZtPgyUKfYwzWtLn66vo" ssh svc-computelab@lego-cg1-qs-100
