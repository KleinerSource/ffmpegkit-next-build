#!/usr/bin/env python3
"""Build unmodified FFmpegKitNext with its own Apple platform adaptations."""
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
LOCK = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
MODULES = ("libavcodec", "libavdevice", "libavfilter", "libavformat",
           "libavutil", "libswresample", "libswscale", "ffmpegkit")
EXCLUDED_HEADERS = {
    "libavcodec": ("amfdec", "amfenc", "qsv", "vdpau", "dxva2", "d3d11va", "d3d12va",
                   "vulkan_video", "videotoolbox", "mediacodec"),
    "libavutil": ("hwcontext_amf", "hwcontext_amf_internal", "hwcontext_vulkan", "hwcontext_vdpau",
                  "hwcontext_vaapi", "hwcontext_qsv", "hwcontext_opencl", "hwcontext_dxva2",
                  "hwcontext_d3d11va", "hwcontext_d3d12va", "hwcontext_cuda", "hwcontext_videotoolbox",
                  "hwcontext_drm", "hwcontext_mediacodec", "hwcontext_ohcodec"),
}


def run(*args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def checkout(name, path):
    source = LOCK["sources"][name]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--depth", "1", "--branch", source["tag"], source["git"], path)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    origin = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=path, text=True).strip()
    if revision != source["commit"] or origin != source["git"]:
        raise ValueError(f"Wrong source identity: {name}: {origin}@{revision}")


def validate_framework(path):
    info = plistlib.loads((path / "Info.plist").read_bytes())
    rows = info["AvailableLibraries"]
    for variant, architectures in ((None, {"arm64"}), ("simulator", {"arm64", "x86_64"})):
        if not any(row.get("SupportedPlatform") == "ios"
                   and row.get("SupportedPlatformVariant") == variant
                   and architectures <= set(row["SupportedArchitectures"]) for row in rows):
            raise ValueError(f"Missing iOS {variant or 'device'} architectures: {path.name}")
    for row in rows:
        framework = path / row["LibraryIdentifier"] / row["LibraryPath"]
        if not (framework / path.stem).is_file():
            raise ValueError(f"Missing framework executable: {framework}")
    return rows


def package(upstream):
    candidates = list((upstream / "prebuilt").glob("bundle-apple-xcframework-ios-*"))
    if len(candidates) != 1:
        raise ValueError(f"Expected one official iOS bundle, got {candidates}")
    destination = ROOT / "dist" / "pods" / "FFmpegKitNext"
    if destination.exists():
        shutil.rmtree(destination)
    frameworks = destination / "Frameworks"
    frameworks.mkdir(parents=True)
    versions = {}
    for module in MODULES:
        target = frameworks / f"{module}.xcframework"
        shutil.copytree(candidates[0] / target.name, target)
        rows = validate_framework(target)
        for row in rows:
            framework = target / row["LibraryIdentifier"] / row["LibraryPath"]
            # FFmpegKitNext only supplies the ffmpegkit module map. Expose the
            # public libav headers to Swift without changing a library binary.
            if module != "ffmpegkit":
                modules = framework / "Modules"
                modules.mkdir(exist_ok=True)
                excluded = "".join(f'  exclude header "{header}.h"\n'
                                   for header in EXCLUDED_HEADERS.get(module, ())
                                   if (framework / "Headers" / f"{header}.h").exists())
                (modules / "module.modulemap").write_text(
                    f'framework module {module} [system] {{\n  umbrella "."\n{excluded}  export *\n}}\n',
                    encoding="utf-8")
            version = plistlib.loads((framework / "Info.plist").read_bytes())["CFBundleShortVersionString"]
            if module in versions and versions[module] != version:
                raise ValueError(f"Inconsistent slice versions: {module}")
            versions[module] = version
    manifest = dict(LOCK, libav_versions=versions)
    manifest["build_revision"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest["source_revisions"] = {
        path.name: subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
        for path in (upstream / "src").iterdir() if (path / ".git").exists()
    }
    (destination / "native-versions.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(upstream / "tools" / "license", destination / "Licenses")
    shutil.copy(upstream / "LICENSE", destination / "Licenses" / "FFmpegKitNext.LICENSE")
    # Preserve the official package and framework names; only adjust local paths.
    spm = (candidates[0] / "Package.swift").read_text(encoding="utf-8")
    for module in MODULES:
        spm = spm.replace(f'path: "{module}.xcframework"', f'path: "Frameworks/{module}.xcframework"')
    (destination / "Package.swift").write_text(spm, encoding="utf-8")
    (destination / "FFmpegKitNext.podspec").write_text("""Pod::Spec.new do |s|
  s.name = 'FFmpegKitNext'
  s.version = '9.0.2'
  s.summary = 'Official FFmpegKitNext and FFmpeg Apple binaries'
  s.homepage = 'https://github.com/arthenica/ffmpeg-kit-next'
  s.authors = { 'Arthenica' => 'info@arthenica.com' }
  s.license = { :type => 'LGPL-3.0', :file => 'Licenses/FFmpegKitNext.LICENSE' }
  s.source = { :http => 'https://github.com/KleinerSource/ffmpegkit-next-build/releases/download/RELEASE/ffmpegkit-next-ios.zip' }
  s.ios.deployment_target = '16.0'
  s.vendored_frameworks = 'Frameworks/*.xcframework'
  s.preserve_paths = 'Licenses/**/*', 'native-versions.json'
end
""".replace("RELEASE", LOCK["release"]), encoding="utf-8")
    dist = ROOT / "dist"
    (dist / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = dist / "ffmpegkit-next-ios.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted((dist / "pods").rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(dist).as_posix())
        output.write(dist / "release-manifest.json", "release-manifest.json")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")


def main():
    upstream = ROOT / ".work" / "upstream"
    checkout("FFmpegKitNext", upstream)
    checkout("FFmpeg", upstream / "src" / "ffmpeg")
    if sys.platform != "darwin":
        raise SystemExit("Apple build requires macOS + Xcode 26 + Nix")
    if "--package-only" not in sys.argv:
        run("bash", "nix-ios.sh", "-p", "xcode26", *LOCK["options"], cwd=upstream)
    if subprocess.check_output(["git", "diff", "--name-only"], cwd=upstream, text=True).strip():
        # Official scripts generate/autoreconf files in apple/. Those are not
        # maintained patches; preserve a complete diff for artifact provenance.
        diff = subprocess.check_output(["git", "diff"], cwd=upstream)
        (ROOT / "dist").mkdir(exist_ok=True)
        (ROOT / "dist" / "official-build-adaptations.diff").write_bytes(diff)
    package(upstream)


if __name__ == "__main__":
    main()
