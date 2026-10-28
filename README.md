# Official FFmpegKitNext Apple builds

This repository contains only build and distribution code. FFmpegKitNext is
checked out at v9.0.2 and FFmpeg at n9.0.2 directly from their official repositories.
`sources.lock.json` fixes both commits and all build options. External libraries
and the Nix toolchain follow the pinned FFmpegKitNext source and flake.lock.

On macOS with Xcode 26 and Nix, run `python3 build.py`. The official
`nix-ios.sh -p xcode26` pipeline creates dynamic frameworks. Custom ffkit protocols
are disabled. Upstream Apple/logging adaptations remain upstream-owned.
We add public-header Swift module maps and a CocoaPods specification; no FFmpeg
or FFmpegKitNext source patch is maintained here.

Releases are versioned and never overwritten. `ffmpegkit-next-ios.zip`, its
SHA-256 and `release-manifest.json` contain iOS arm64 and arm64/x86_64 Simulator
slices, upstream licenses and source revisions. Consume the local
`pods/FFmpegKitNext` directory through CocoaPods or SPM after verifying the archive.
An App build must never run `build.py`.
