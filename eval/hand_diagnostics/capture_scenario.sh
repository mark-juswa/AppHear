#!/bin/sh
# Controlled hand-diagnostic capture on an ALREADY RUNNING emulator/device. Does not touch app source or settings.
#   usage: capture_scenario.sh <scenario-name> <out-dir> [seconds=60] [serial=emulator-5554]
# Steps: force-stop the app (resets the analyzer: the per-frame AppHearV3 log is capped at 240 frames per analyzer start and the
# 30 s counters are cumulative), clear logcat, launch to the recognition screen, then record <seconds> of the four AppHear tags
# and take screenshots every 10 s so the scenario can be verified visually afterwards. Screenshots contain the user's camera
# image: they stay in <out-dir> (keep it outside the repo).
set -eu
NAME=${1:?scenario name}; OUT=${2:?out dir}; SECS=${3:-60}; SER=${4:-emulator-5554}
PKG=com.example.apphear
A="adb -s $SER"
# Device identity + thermal/battery state, so a physical-phone run can never be mistaken for an emulator run (they are kept separate).
devmeta() {
  P() { $A shell getprop "$1" | tr -d '\r'; }
  QEMU="$(P ro.kernel.qemu)$(P ro.boot.qemu)"; HWN="$(P ro.hardware)"; MODEL="$(P ro.product.model)"
  if [ -z "$MODEL" ]; then CLASS=unknown                                   # adb gave nothing: never guess
  elif [ "$QEMU" != "" ] && [ "$QEMU" != "0" ] && [ "$QEMU" != "00" ]; then CLASS=emulator
  else case "$HWN" in ranchu*|goldfish*|*emu*) CLASS=emulator ;; *) CLASS=physical ;; esac; fi
  echo "device_class=$CLASS manufacturer=$(P ro.product.manufacturer) model=$(P ro.product.model) android=$(P ro.build.version.release) sdk=$(P ro.build.version.sdk) abi=$(P ro.product.cpu.abi) soc=$(P ro.soc.model) fingerprint=$(P ro.build.fingerprint)"
  echo "battery: $($A shell dumpsys battery | tr -d '\r' | grep -E 'level|temperature|powered' | tr -s ' ' | tr '\n' ';')"
  echo "thermal_status: $($A shell dumpsys thermalservice 2>/dev/null | tr -d '\r' | grep -m1 -E 'Thermal Status|mStatus' | tr -s ' ')"
  echo "power_saver(low_power)=$($A shell settings get global low_power | tr -d '\r') app_version=$($A shell dumpsys package com.example.apphear | tr -d '\r' | grep -m1 versionName | tr -d ' ')"
}
mkdir -p "$OUT/${NAME}_shots"
$A shell am force-stop $PKG
$A logcat -c
$A shell am start -W -n $PKG/.SplashActivity >/dev/null
# home screen -> "Start now" (coordinates measured on the 1080x2400 emulator screen)
i=0; until $A shell dumpsys activity activities | grep -q "topResumedActivity.*MainActivity"; do i=$((i+1)); [ $i -gt 30 ] && { echo "HOME_NOT_REACHED" >&2; exit 2; }; sleep 1; done
sleep 1; $A shell input tap 247 1626
i=0; until $A shell dumpsys activity activities | grep -q "topResumedActivity.*RecognitionActivity"; do i=$((i+1)); [ $i -gt 30 ] && { echo "RECOGNITION_NOT_REACHED" >&2; exit 3; }; sleep 1; done
START=$(date +%s)
echo "capture_start_epoch=$START scenario=$NAME seconds=$SECS serial=$SER" > "$OUT/${NAME}.meta"
{ echo "--- device at start"; devmeta; } >> "$OUT/${NAME}.meta"
# logcat in the background for the whole window, then stop it
$A logcat -v threadtime -s AppHearDetect:I AppHearV3:I AppHearPhone:I AppHearRecognition:I > "$OUT/${NAME}.log" 2>&1 &
LPID=$!
n=0
while [ $(( $(date +%s) - START )) -lt "$SECS" ]; do
  $A exec-out screencap -p > "$OUT/${NAME}_shots/t$(( $(date +%s) - START )).png" 2>/dev/null || true
  sleep 10; n=$((n+1))
done
# make sure the final 30 s counter line (t=60) is flushed
sleep 4
kill $LPID 2>/dev/null || true
$A logcat -d -b crash > "$OUT/${NAME}.crash.log" 2>&1 || true
echo "capture_end_epoch=$(date +%s)" >> "$OUT/${NAME}.meta"
{ echo "--- device at end"; devmeta; } >> "$OUT/${NAME}.meta"
echo "done $NAME: $(grep -c AppHearV3 "$OUT/${NAME}.log") per-frame lines, $(grep -c AppHearDetect "$OUT/${NAME}.log") summaries, $(ls "$OUT/${NAME}_shots" | wc -l) screenshots"
