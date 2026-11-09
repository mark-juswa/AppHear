#!/bin/sh
# One labelled webcam session captured TWICE at the same moment: clean frames on the host (for the offline probe) and the app's shadow log
# (AppHearEcho) on a running emulator/device that uses the same camera. The ground truth schedule carries wall-clock windows, so shadow
# decisions can be joined to manually specified truth afterwards.
#   usage: run_session_with_shadow.sh <out_dir> <subject> <core|hard|all> <python-with-opencv> [serial=emulator-5554] [only=seg1,seg2] [tag]
set -eu
OUT=${1:?out dir}; SUBJ=${2:?subject}; SET=${3:?set}; PY=${4:?python}; SER=${5:-emulator-5554}; ONLY=${6:-}; TAG=${7:-}
A="adb -s $SER"; PKG=com.example.apphear
D="$OUT/${SUBJ}_${SET}${TAG:+_$TAG}"; mkdir -p "$D"
echo "host_epoch=$(date +%s) device_epoch=$($A shell date +%s | tr -d '\r') subject=$SUBJ set=$SET serial=$SER" > "$D/clock.meta"
$A shell am force-stop $PKG; $A logcat -c
$A shell am start -W -n $PKG/.SplashActivity >/dev/null 2>&1 || true
i=0; until $A shell dumpsys activity activities | grep -q "topResumedActivity.*MainActivity"; do i=$((i+1)); [ $i -gt 45 ] && { echo HOME_NOT_REACHED >&2; exit 2; }; sleep 1; done
sleep 1; $A shell input tap 247 1626
i=0; until [ "$($A logcat -d -s AppHearEcho:I | grep -c apphear.hand_echo_shadow)" -ge 5 ]; do i=$((i+1)); [ $i -gt 60 ] && { echo "NO_ECHO_LOG (is the APK built with -PhandEchoShadow=true?)" >&2; exit 3; }; sleep 1; done
$A logcat -v epoch -s AppHearEcho:I AppHearDetect:I > "$D/shadow.log" 2>&1 &
LPID=$!
"$PY" -m eval.hand_diagnostics.capture_pose_session "$D/frames" --set "$SET" --subject "$SUBJ" ${ONLY:+--only "$ONLY"}
sleep 4; kill $LPID 2>/dev/null || true
$A logcat -d -b crash > "$D/crash.log" 2>&1 || true
echo "shadow lines: $(grep -c apphear.hand_echo_shadow "$D/shadow.log"); frames: $(ls "$D/frames"/*.png | wc -l); crash lines: $(grep -vc 'beginning of' "$D/crash.log" || true)"
