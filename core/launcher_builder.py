"""Tự clone smtv-home (nvt-ak/smtv-home, nhánh smtv-main), build launcher APK bằng Gradle.

Cần trên máy chạy app: git, JDK 17–21 (có jlink; Android Studio có sẵn trong thư mục jbr), Android SDK.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
from typing import Callable, Dict, List, Optional

REPO_URL = "https://github.com/nvt-ak/smtv-home.git"
BRANCH = "smtv-main"
APK_REL = os.path.join("launcher", "app", "build", "outputs", "apk", "release", "app-release.apk")
_WIN = sys.platform.startswith("win")
_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _WIN else 0


def cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".smarttv-manager", "smtv-home")
    os.makedirs(d, exist_ok=True)
    return d


def cached_apk_path() -> str:
    return os.path.join(cache_dir(), "smtv-home.apk")


def _java_info(home: str) -> Optional[Dict]:
    exe = os.path.join(home, "bin", "java.exe" if _WIN else "java")
    if not os.path.isfile(exe):
        return None
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=20,
                             creationflags=_NOWIN).stderr
    except Exception:
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out or "")
    if not m:
        return None
    major = int(m.group(1))
    if major == 1:
        major = int(m.group(2) or 8)
    jlink = os.path.isfile(os.path.join(home, "bin", "jlink.exe" if _WIN else "jlink"))
    return {"home": home, "major": major, "has_jlink": jlink}


def find_java() -> Optional[Dict]:
    cands: List[str] = []
    if os.environ.get("JAVA_HOME"):
        cands.append(os.environ["JAVA_HOME"])
    for pat in (r"C:\Program Files\Android\Android Studio*\jbr",
                r"C:\Program Files\Eclipse Adoptium\jdk-*",
                r"C:\Program Files\Java\jdk-*",
                r"C:\Program Files\Microsoft\jdk-*",
                "/usr/lib/jvm/*", "/opt/homebrew/opt/openjdk@17"):
        cands += sorted(glob.glob(pat), reverse=True)
    jexe = shutil.which("java")
    if jexe:
        cands.append(os.path.dirname(os.path.dirname(os.path.realpath(jexe))))
    best = None
    for c in cands:
        info = _java_info(c)
        if info and info["has_jlink"] and 17 <= info["major"] <= 21:
            return info
        if info and best is None:
            best = info
    return best


def find_sdk() -> Optional[str]:
    cands = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk") if _WIN else None,
             os.path.expanduser("~/Android/Sdk"), os.path.expanduser("~/Library/Android/sdk")]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "platforms")) or (c and os.path.isdir(os.path.join(c, "cmdline-tools"))):
            return c
    return None


def check_prereqs() -> Dict:
    git = shutil.which("git")
    java = find_java()
    sdk = find_sdk()
    missing = []
    if not git:
        missing.append("Git (https://git-scm.com)")
    if not java:
        missing.append("JDK 17–21 (Android Studio có sẵn trong thư mục jbr)")
    elif not (17 <= java["major"] <= 21):
        missing.append(f"JDK {java['major']} ({java['home']}) không phù hợp — cần JDK 17–21")
    elif not java["has_jlink"]:
        missing.append(f"JDK tại {java['home']} thiếu jlink (đang là JRE) — cần bản JDK")
    if not sdk:
        missing.append("Android SDK (cài Android Studio hoặc command-line tools, đặt ANDROID_HOME)")
    return {"ok": not missing, "missing": missing, "git": git,
            "java": java, "sdk": sdk}


def _run(cmd, cwd, env, on_step, tag, timeout):
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", creationflags=_NOWIN)
    tail: List[str] = []
    import threading
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    try:
        for line in p.stdout:
            line = line.rstrip()
            if not line:
                continue
            tail.append(line)
            del tail[:-25]
            if tag and len(tail) % 1 == 0:
                on_step(tag, line[:200])
        rc = p.wait()
    finally:
        timer.cancel()
    return rc, "\n".join(tail)


def build_apk(on_step: Callable[[str, str], None], tv_sdk: Optional[int] = None,
              ref: Optional[str] = None) -> str:
    pre = check_prereqs()
    if not pre["ok"]:
        raise Exception("Thiếu công cụ build: " + "; ".join(pre["missing"]))
    root = os.path.join(cache_dir(), "repo")
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["JAVA_HOME"] = pre["java"]["home"]
    env["ANDROID_HOME"] = pre["sdk"]
    env["ANDROID_SDK_ROOT"] = pre["sdk"]
    env["PATH"] = os.path.join(pre["java"]["home"], "bin") + os.pathsep + env.get("PATH", "")

    if os.path.isdir(os.path.join(root, ".git")):
        on_step("build_fetch", "cập nhật mã nguồn smtv-home")
        rc, tail = _run([pre["git"], "fetch", "--depth", "1", "origin", ref or BRANCH], root, env, on_step, None, 300)
        if rc == 0:
            rc, tail = _run([pre["git"], "reset", "--hard", "FETCH_HEAD"], root, env, on_step, None, 120)
    else:
        on_step("build_clone", f"git clone {REPO_URL}")
        shutil.rmtree(root, ignore_errors=True)
        rc, tail = _run([pre["git"], "clone", "--depth", "1", "--branch", BRANCH, REPO_URL, root], cache_dir(), env, on_step, "build_clone", 600)
        if rc == 0 and ref:
            rc, tail = _run([pre["git"], "fetch", "--depth", "1", "origin", ref], root, env, on_step, None, 300)
            if rc == 0:
                rc, tail = _run([pre["git"], "checkout", "FETCH_HEAD"], root, env, on_step, None, 120)
    if rc != 0:
        raise Exception("git thất bại (kiểm tra mạng/GitHub):\n" + tail)

    launcher = os.path.join(root, "launcher")
    try:
        gtxt = open(os.path.join(launcher, "app", "build.gradle"), encoding="utf-8").read()
        m = re.search(r"^\s*minSdk\s+(\d+)\s*$", gtxt, re.M)
        min_sdk = int(m.group(1)) if m else None
    except Exception:
        min_sdk = None
    if tv_sdk and min_sdk and tv_sdk < min_sdk:
        raise Exception(f"TV chạy SDK {tv_sdk} thấp hơn minSdk {min_sdk} của launcher — không thể cài. Chưa build gì.")

    lp = os.path.join(launcher, "local.properties")
    if not os.path.isfile(lp):
        with open(lp, "w", encoding="utf-8") as f:
            f.write("sdk.dir=" + pre["sdk"].replace("\\", "/") + "\n")
    out_apk = os.path.join(root, APK_REL)
    if os.path.isfile(out_apk):
        os.remove(out_apk)
    on_step("build_gradle", "gradlew assembleRelease (lần đầu có thể mất vài phút để tải Gradle/thư viện)")
    cmd = ([os.path.join(launcher, "gradlew.bat")] if _WIN else ["sh", os.path.join(launcher, "gradlew")]) + \
        ["assembleRelease", "-q", "--console=plain"]
    rc, tail = _run(cmd, launcher, env, on_step, "build_gradle", 1800)
    if rc != 0 or not os.path.isfile(out_apk):
        raise Exception("Build thất bại:\n" + tail)
    shutil.copyfile(out_apk, cached_apk_path())
    on_step("build_done", f"{os.path.getsize(out_apk) // 1024} KB")
    return cached_apk_path()
