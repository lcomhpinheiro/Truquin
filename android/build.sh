#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SDK="${TRUCO_ANDROID_SDK:-/tmp/truco-android-sdk}"
TOOLS="$SDK/android-16"
JAR="$SDK/android-36/android.jar"
mkdir -p build/android/{gen,classes,dex} dist
"$TOOLS/aapt2" compile --dir android/res -o build/android/resources.zip
"$TOOLS/aapt2" link -o build/android/base.apk -I "$JAR" --manifest android/AndroidManifest.xml --java build/android/gen -A android/assets build/android/resources.zip
javac --release 8 -encoding UTF-8 -cp "$JAR" -d build/android/classes android/src/br/com/trucodamesa/*.java build/android/gen/br/com/trucodamesa/R.java
"$TOOLS/d8" --lib "$JAR" --min-api 23 --output build/android/dex build/android/classes/br/com/trucodamesa/*.class
python3 - <<'PY'
import zipfile
with zipfile.ZipFile('build/android/base.apk','a') as z:z.write('build/android/dex/classes.dex','classes.dex')
PY
if [ ! -f build/android/local.keystore ]; then
 keytool -genkeypair -keystore build/android/local.keystore -storepass android -keypass android -alias truco -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Truco da Mesa Local' -noprompt
fi
"$TOOLS/zipalign" -f 4 build/android/base.apk build/android/aligned.apk
"$TOOLS/apksigner" sign --ks build/android/local.keystore --ks-key-alias truco --ks-pass pass:android --key-pass pass:android --out dist/Truco-da-Mesa.apk build/android/aligned.apk
"$TOOLS/apksigner" verify --verbose dist/Truco-da-Mesa.apk
