#!/usr/bin/env python3
"""Compile a real CocoaPods application using the freshly built official dylibs."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
HARNESS = ROOT / ".work" / "PodsSmoke"


def run(*args, cwd=HARNESS):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    HARNESS.mkdir(parents=True, exist_ok=True)
    (HARNESS / "Smoke.swift").write_text('''import UIKit
import KSPlayer
import libavutil
@main class Smoke: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        print(String(cString: av_version_info()))
        return true
    }
}
''', encoding="utf-8")
    run("ruby", "-rxcodeproj", "-e", '''p = Xcodeproj::Project.new('PodsSmoke.xcodeproj')
t = p.new_target(:application, 'PodsSmoke', :ios, '16.0')
t.source_build_phase.add_file_reference(p.main_group.new_file('Smoke.swift'))
t.build_configurations.each do |c|
  c.build_settings['SWIFT_VERSION'] = '5.9'
  c.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = 'org.ohmymedia.native-smoke'
  c.build_settings['GENERATE_INFOPLIST_FILE'] = 'YES'
  c.build_settings['CODE_SIGNING_ALLOWED'] = 'NO'
end
p.save
''')
    player = (ROOT / ".work" / "KSPlayer").as_posix()
    kit = (ROOT / "dist" / "pods" / "FFmpegKitNext").as_posix()
    (HARNESS / "Podfile").write_text(f'''platform :ios, '16.0'
use_frameworks! :linkage => :static
target 'PodsSmoke' do
  pod 'KSPlayer', :path => '{player}'
  pod 'DisplayCriteria', :path => '{player}'
  pod 'KSFFmpegBridge', :path => '{player}'
  pod 'FFmpegKitNext', :path => '{kit}'
end
''', encoding="utf-8")
    run("pod", "install")
    run("xcodebuild", "-workspace", "PodsSmoke.xcworkspace", "-scheme", "PodsSmoke",
        "-destination", "generic/platform=iOS", "-configuration", "Release", "CODE_SIGNING_ALLOWED=NO", "build")


if __name__ == "__main__":
    main()
