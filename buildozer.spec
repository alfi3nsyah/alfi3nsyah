[app]
title = Seismic Sentinel
package.name = seismicsentinel
package.domain = org.alfiansyah
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
version = 1.0

# Kunci dependensi stabil
requirements = python3,kivy,requests,urllib3,charset_normalizer,idna,certifi

orientation = portrait
fullscreen = 0

# Target Android SDK & NDK stabil
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a

android.permissions = INTERNET,VIBRATE,WAKE_LOCK

[buildozer]
log_level = 2
warn_on_root = 1
