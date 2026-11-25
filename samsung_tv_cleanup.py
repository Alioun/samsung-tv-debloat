#!/usr/bin/env python3
"""Samsung Tizen TV cleanup: close bloat apps and block Samsung ads + tracking at the router.

This handles the NETWORK layer only (DNS blocking + closing apps). Removing apps, killing
telemetry at the source and a Plex/YouTube launcher need root -- see GUIDE.md for that flow
(Developer Mode -> Apps2Samsung -> vetro). The DNS block here is a good standalone layer and
stacks under root.

Python 3.9+, standard library only. Pick your router:

  python3 samsung_tv_cleanup.py --tv 192.168.1.50                        # just close bloat apps
  python3 samsung_tv_cleanup.py --fritz-device S95B                      # FRITZ!Box
  python3 samsung_tv_cleanup.py --unifi-host 192.168.1.1 --unifi-tv-mac AA:BB:CC:DD:EE:FF
  python3 samsung_tv_cleanup.py --print-blocklist                        # Pi-hole / AdGuard Home
"""
import argparse
import getpass
import hashlib
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Ad, viewing-tracking (ACR), remote-management and crash-report hosts. Deliberately leaves out
# samsungcloudsolution.com/.net as a whole and samsungotn.net: blocking those breaks the app
# store and firmware updates. For the same reason block only gpm.samsungqbe.com (ads), NOT the
# bare samsungqbe.com -- that parent also hosts osb.samsungqbe.com, the app-store backend, and
# blocking it makes the Apps panel fail with "server isn't available".
BLOCKLIST = [
    "samsungads.com",
    "samsungadhub.com",
    "ads.samsung.com",
    "samsungacr.com",
    "gpm.samsungqbe.com",
    "samsungrm.net",
    "cpu.samsungelectronics.com",
    "prderrordumphsm.samsungcloudsolution.com",
    "noticecdn.samsungcloudsolution.com",
    "notice.samsungcloudsolution.com",
]

KNOWN_APPS = {
    "111299001912": "YouTube",
    "3201512006963": "Plex",
    "3201907018807": "Netflix",
    "3201910019365": "Prime Video",
    "3201901017640": "Disney+",
    "3201606009684": "Spotify",
    "3201807016597": "Apple TV",
    "3201908019041": "Apple Music",
    "3202010022079": "Browser",
    "3201511006428": "Rakuten TV",
    "3201707014366": "Joyn",
    "3201806016432": "DAZN",
    "3202203026841": "Xbox",
    "3202110025305": "GeForce NOW",
}
KEEP_DEFAULT = "YouTube,Plex"
PROFILE_NAME = "Samsung TV"

CHECKLIST = """
CHECKLIST: do these on the TV with the remote
  1. Settings > General & Privacy > Terms & Privacy > Privacy Choices:
     turn OFF Viewing Information Services, Interest-Based Advertisement, Voice Recognition Services.
  2. Settings > General & Privacy > Start Screen Option: turn OFF "Start with Home Screen".
  3. Home > Apps > gear icon: delete every app you don't use (preinstalled system apps
     such as Samsung TV Plus, Gaming Hub or SmartThings can't be removed).
  4. Settings > Support > Device Care > Start Device Care.
  5. Hold the remote's power button until the Samsung logo appears (full restart).
"""


def http(url, data=None, method=None, timeout=10, headers=None, context=None, json_body=None):
    if json_body is not None:
        body = json.dumps(json_body).encode()
    elif isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
    else:
        body = data
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout, context=context) as r:
        return r.read().decode()


# ---------------------------------------------------------------- TV

def tv_cleanup(ip, keep):
    info = json.loads(http(f"http://{ip}:8001/api/v2/"))["device"]
    print(f"TV: {info['name']} ({info['modelName']}), Tizen, developerMode={info['developerMode']}")
    for app_id, name in KNOWN_APPS.items():
        try:
            app = json.loads(http(f"http://{ip}:8001/api/v2/applications/{app_id}", timeout=4))
        except Exception:
            continue
        line = f"  installed: {name:<12} running={app.get('running')}"
        if app.get("running") and name not in keep:
            http(f"http://{ip}:8001/api/v2/applications/{app_id}", method="DELETE")
            line += "  -> closed"
        print(line)


# ---------------------------------------------------------------- FRITZ!Box

class Fritz:
    def __init__(self, host, user, password):
        self.base = f"http://{host}"
        challenge_xml = ET.fromstring(http(f"{self.base}/login_sid.lua?version=2"))
        user = user or challenge_xml.findtext("Users/User[@last='1']") or ""
        challenge = challenge_xml.findtext("Challenge")
        if not challenge.startswith("2$"):
            sys.exit("FRITZ!OS too old: needs 7.24 or newer (PBKDF2 login)")
        _, i1, s1, i2, s2 = challenge.split("$")
        h1 = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(s1), int(i1))
        h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(s2), int(i2))
        res = ET.fromstring(http(f"{self.base}/login_sid.lua?version=2",
                                 {"username": user, "response": f"{s2}${h2.hex()}"}))
        self.sid = res.findtext("SID")
        if set(self.sid) == {"0"}:
            sys.exit(f"FRITZ!Box login failed for user '{user}'")
        print(f"FRITZ!Box: logged in as {user}")

    def page(self, page, **extra):
        return http(f"{self.base}/data.lua",
                    {"sid": self.sid, "xhr": 1, "lang": "de", "page": page, **extra})

    def apply(self, page, **fields):
        res = json.loads(self.page(page, apply="", **fields))["data"]
        if res.get("apply") != "ok":
            sys.exit(f"FRITZ!Box rejected change on {page}: {res}")

    def logout(self):
        http(f"{self.base}/login_sid.lua?version=2", {"sid": self.sid, "logout": 1})

    def merge_blocklist(self):
        data = json.loads(self.page("kids_blacklist", xhrId="all"))["data"]
        current = [e["url"] for e in data["list"]]
        missing = [d for d in BLOCKLIST if d not in current]
        if missing:
            self.apply("kids_blacklist", listtype="black", urllist="\r".join(current + missing))
        print(f"  block list: {len(current)} existing, {len(missing)} added")

    def ensure_profile(self):
        html = self.page("kidLis", xhrId="all")
        m = re.search(r'<option value="(filtprof\d+)"[^>]*>' + re.escape(PROFILE_NAME) + "<", html)
        if m:
            print(f"  profile '{PROFILE_NAME}' already exists")
            return m.group(1)
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        fields = {f"hours_{d}": "24" for d in days} | {f"minutes_{d}": "00" for d in days}
        self.apply("kids_profileedit", oldpage="/internet/kids_profileedit.lua", edit="",
                   name=PROFILE_NAME, time="unlimited", budget="unlimited", parental="on",
                   filtertype="black", netappschosen="", **fields)
        print(f"  profile '{PROFILE_NAME}' created (unlimited time, block list filter)")
        return self.ensure_profile()

    def device_profiles(self):
        html = self.page("kidLis", xhrId="all")
        rows = {}
        for m in re.finditer(r'<td class="name" title="([^"]*)".*?<select[^>]*name="(profile:[^"]+)"[^>]*>(.*?)</select>',
                             html, re.S):
            sel = re.search(r'<option value="([^"]+)" selected', m.group(3))
            rows[m.group(2)] = (m.group(1), sel.group(1) if sel else None)
        return rows

    def assign(self, device_name, profile_id):
        rows = self.device_profiles()
        matches = [k for k, (title, _) in rows.items() if title == device_name]
        if len(matches) != 1:
            names = sorted({t for t, _ in rows.values()})
            sys.exit(f"Expected one device named '{device_name}', found {len(matches)}. Devices: {', '.join(names)}")
        key = matches[0]
        if rows[key][1] == profile_id:
            print(f"  '{device_name}' already uses '{PROFILE_NAME}'")
            return
        form = {k: prof for k, (_, prof) in rows.items() if prof}
        form[key] = profile_id
        self.apply("kidLis", **form)
        after = self.device_profiles()
        changed = [t for k, (t, p) in rows.items() if k in after and after[k][1] != p and t != device_name]
        if changed:
            print(f"  WARNING: other devices changed profile: {changed}")
        print(f"  '{device_name}' now uses '{PROFILE_NAME}'")


# ---------------------------------------------------------------- UniFi
# NOTE: UniFi's content-filter API is undocumented (reverse-engineered from the web UI) and has
# shifted between UniFi OS versions. This is best-effort: it UPDATES an existing Content Filter
# policy you create once in the UI. If anything looks off, do it in the UI (see GUIDE.md).

class UniFi:
    def __init__(self, host, api_key, site="default"):
        self.base = f"https://{host}"
        self.site = site
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE  # UniFi gateways use a self-signed cert
        self.key = api_key
        print(f"UniFi: gateway {host}, site '{site}' (API is unofficial; verify in the UI afterwards)")

    def _req(self, path, method="GET", body=None):
        headers = {"X-API-KEY": self.key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        raw = http(f"{self.base}{path}", method=method, json_body=body, headers=headers, context=self.ctx)
        return json.loads(raw) if raw.strip() else {}

    def policies(self):
        data = self._req(f"/proxy/network/v2/api/site/{self.site}/content-filtering")
        return data.get("data", data) if isinstance(data, dict) else data

    def apply_block(self, policy_name, tv_mac):
        pols = self.policies()
        match = [p for p in pols if p.get("name") == policy_name]
        if not match:
            names = [p.get("name") for p in pols] or ["(none)"]
            sys.exit(f"No Content Filter named '{policy_name}'. Create one in the UI first "
                     f"(Settings > CyberSecure > Content Filter), scope it to the TV, then re-run. "
                     f"Existing policies: {names}")
        pol = match[0]
        pid = pol.get("_id") or pol.get("id")
        block = pol.get("block_list") or []
        merged = block + [d for d in BLOCKLIST if d not in block]
        macs = pol.get("client_macs") or []
        if tv_mac and tv_mac.lower() not in [m.lower() for m in macs]:
            macs = macs + [tv_mac.lower()]
        body = dict(pol)
        body["block_list"] = merged
        body["client_macs"] = macs
        self._req(f"/proxy/network/v2/api/site/{self.site}/content-filtering/{pid}", "PUT", body)
        added = len(merged) - len(block)
        print(f"  Content Filter '{policy_name}': {len(block)} existing + {added} added "
              f"= {len(merged)} domains, scoped to {len(macs)} device(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tv", help="TV IP address")
    ap.add_argument("--keep", default=KEEP_DEFAULT, help=f"apps left running (default {KEEP_DEFAULT})")
    ap.add_argument("--fritz-device", help="TV's name as shown in FRITZ!Box > Internet > Filter")
    ap.add_argument("--fritz-host", default="fritz.box")
    ap.add_argument("--fritz-user", help="defaults to the last user that logged in")
    ap.add_argument("--fritz-password-file", help="read password from file instead of prompting")
    ap.add_argument("--unifi-host", help="UniFi gateway IP (UDM/UCG/UDR/Express)")
    ap.add_argument("--unifi-filter", default="Samsung TV",
                    help="name of the Content Filter policy to update (create it in the UI first)")
    ap.add_argument("--unifi-tv-mac", help="TV MAC address, to scope the filter to just the TV")
    ap.add_argument("--unifi-site", default="default")
    ap.add_argument("--unifi-key-file", help="read UniFi API key from file instead of prompting")
    ap.add_argument("--print-blocklist", action="store_true")
    a = ap.parse_args()

    if a.print_blocklist:
        print("\n".join(BLOCKLIST))
        return
    if not (a.tv or a.fritz_device or a.unifi_host):
        ap.error("pass --tv and/or a router target (--fritz-device or --unifi-host)")
    if a.tv:
        tv_cleanup(a.tv, set(a.keep.split(",")))
    if a.fritz_device:
        pw = (open(a.fritz_password_file).read().rstrip("\r\n") if a.fritz_password_file
              else getpass.getpass("FRITZ!Box password: "))
        box = Fritz(a.fritz_host, a.fritz_user, pw)
        try:
            box.merge_blocklist()
            box.assign(a.fritz_device, box.ensure_profile())
        finally:
            box.logout()
    if a.unifi_host:
        key = (open(a.unifi_key_file).read().strip() if a.unifi_key_file
               else getpass.getpass("UniFi API key: "))
        UniFi(a.unifi_host, key, a.unifi_site).apply_block(a.unifi_filter, a.unifi_tv_mac)
    print(CHECKLIST)


if __name__ == "__main__":
    main()
