#!/usr/bin/env python3
"""Samsung Tizen TV cleanup: close bloat apps and block Samsung's ad and tracking servers.

This script works on the network only. It blocks DNS names at the router and closes apps that
run in the background. Removing apps, turning off telemetry on the TV, and a launcher for apps
such as Plex and YouTube need root. GUIDE.md covers root: Developer Mode, then Apps2Samsung, then
vetro. The DNS block works without root and adds a second layer to a rooted TV.

The script needs Python 3.9 or later and only the standard library. Pick your router:

  python3 samsung_tv_cleanup.py --tv 192.168.1.50                        # close bloat apps only
  python3 samsung_tv_cleanup.py --fritz-device S95B                      # FRITZ!Box
  python3 samsung_tv_cleanup.py --unifi-host 192.168.1.1 --unifi-tv-mac AA:BB:CC:DD:EE:FF
  python3 samsung_tv_cleanup.py --print-blocklist                        # Pi-hole or AdGuard Home
"""
import argparse
import getpass
import hashlib
import html
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects, so the SID and X-API-KEY headers never go to a different origin.

    urllib then raises the 3xx response as an error."""

    def redirect_request(self, *args):
        return None

# Hosts for ads, viewing tracking (ACR), remote management, and crash reports. The list leaves
# out samsungotn.net and the whole of samsungcloudsolution.com and samsungcloudsolution.net,
# because blocking them breaks the app store and firmware updates. For the same reason it blocks
# gpm.samsungqbe.com, the ad host, and leaves the bare samsungqbe.com alone. That parent domain
# also hosts osb.samsungqbe.com, the app store backend. Blocking it makes the Apps panel fail
# with "server isn't available".
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
     turn OFF Viewing Information Services, Interest-Based Advertisement and
     Voice Recognition Services.
  2. Settings > General & Privacy > Start Screen Option: turn OFF "Start with Home Screen".
  3. Home > Apps > gear icon: delete every app you don't use. Preinstalled system apps,
     such as Samsung TV Plus, Gaming Hub and SmartThings, can't be removed.
  4. Settings > Support > Device Care > Start Device Care.
  5. For a full restart, hold the remote's power button until the Samsung logo appears.
"""


def http(url, data=None, method=None, timeout=10, headers=None, context=None, json_body=None,
         no_redirect=False):
    if json_body is not None:
        body = json.dumps(json_body).encode()
    elif isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
    else:
        body = data
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    handlers = []
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    if no_redirect:
        handlers.append(_NoRedirect)
    opener = urllib.request.build_opener(*handlers)
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode()


# ---------------------------------------------------------------- TV

def tv_cleanup(ip, keep):
    info = json.loads(http(f"http://{ip}:8001/api/v2/"))["device"]
    print(f"TV: {info['name']} ({info['modelName']}), Tizen, developerMode={info['developerMode']}")
    for app_id, name in KNOWN_APPS.items():
        try:
            app = json.loads(http(f"http://{ip}:8001/api/v2/applications/{app_id}", timeout=4))
        except Exception:
            continue  # The app isn't installed or the TV didn't answer. Try the next app.
        running, visible = app.get("running"), app.get("visible")
        line = f"  installed: {name:<12} running={running} visible={visible}"
        if running and name not in keep:
            if visible is not False:
                # Close only apps that the TV reports as hidden. Never close an app that is on
                # screen or whose visibility the TV didn't report.
                line += ", left running because it is on screen or its visibility is unknown"
            else:
                try:
                    http(f"http://{ip}:8001/api/v2/applications/{app_id}", method="DELETE")
                    line += ", closed"
                except Exception as e:  # A failed close must not stop the router steps that follow.
                    line += f", close failed: {e}"
        print(line)


# ---------------------------------------------------------------- FRITZ!Box

class Fritz:
    def __init__(self, host, user, password):
        self.base = f"http://{host}"
        challenge_xml = ET.fromstring(http(f"{self.base}/login_sid.lua?version=2", no_redirect=True))
        block = int(challenge_xml.findtext("BlockTime") or "0")
        if block > 0:
            sys.exit(f"FRITZ!Box login is rate-limited. Wait {block}s and try again.")
        user = user or challenge_xml.findtext("Users/User[@last='1']") or ""
        challenge = challenge_xml.findtext("Challenge") or ""
        if not challenge.startswith("2$"):
            sys.exit("FRITZ!Box sent an unknown login challenge. "
                     "The script needs FRITZ!OS 7.24 or later.")
        _, i1, s1, i2, s2 = challenge.split("$")
        h1 = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(s1), int(i1))
        h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(s2), int(i2))
        res = ET.fromstring(http(f"{self.base}/login_sid.lua?version=2",
                                 {"username": user, "response": f"{s2}${h2.hex()}"}, no_redirect=True))
        self.sid = res.findtext("SID") or ""
        if not self.sid or set(self.sid) == {"0"}:
            wait = int(res.findtext("BlockTime") or "0")
            hint = f" The router blocks logins for {wait}s after failed attempts." if wait else ""
            sys.exit(f"FRITZ!Box login failed for user '{user or '(default)'}'.{hint}")
        print(f"FRITZ!Box: logged in as {user}")

    def page(self, page, **extra):
        return http(f"{self.base}/data.lua",
                    {"sid": self.sid, "xhr": 1, "lang": "de", "page": page, **extra},
                    no_redirect=True)

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

    def _find_profile(self):
        page = self.page("kidLis", xhrId="all")
        m = re.search(r'<option value="(filtprof\d+)"[^>]*>' + re.escape(PROFILE_NAME) + "<", page)
        return m.group(1) if m else None

    def ensure_profile(self):
        pid = self._find_profile()
        if pid:
            print(f"  profile '{PROFILE_NAME}' already exists")
            return pid
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        fields = {f"hours_{d}": "24" for d in days} | {f"minutes_{d}": "00" for d in days}
        self.apply("kids_profileedit", oldpage="/internet/kids_profileedit.lua", edit="",
                   name=PROFILE_NAME, time="unlimited", budget="unlimited", parental="on",
                   filtertype="black", netappschosen="", **fields)
        # Read once more. Recursion would loop forever after a router UI change.
        pid = self._find_profile()
        if not pid:
            sys.exit(f"FRITZ!Box: created profile '{PROFILE_NAME}' but can't find it on re-read. "
                     f"Check Internet > Filter > Access Profiles in the router UI.")
        print(f"  profile '{PROFILE_NAME}' created with unlimited time and the block list filter")
        return pid

    def device_profiles(self):
        # Parse one <tr> at a time, so a row without a dropdown never takes the next row's
        # dropdown. One regex across all rows used to make that mistake.
        rows = {}
        for row in re.split(r"(?=<tr\b)", self.page("kidLis", xhrId="all")):
            nm = re.search(r'<td class="name" title="([^"]*)"', row)
            se = re.search(r'<select[^>]*name="(profile:[^"]+)"[^>]*>(.*?)</select>', row, re.S)
            if not (nm and se):
                continue
            sel = re.search(r'<option value="([^"]+)" selected', se.group(2))
            rows[se.group(1)] = (html.unescape(nm.group(1)), sel.group(1) if sel else None)
        return rows

    def require_device(self, device_name):
        """Check the device name before any write, so a typo can't change the shared list."""
        rows = self.device_profiles()
        if not any(t == device_name for t, _ in rows.values()):
            names = sorted({t for t, _ in rows.values()})
            sys.exit(f"No device named '{device_name}' in FRITZ!Box. Devices: {', '.join(names)}")

    def assign(self, device_name, profile_id):
        rows = self.device_profiles()
        matches = [k for k, (title, _) in rows.items() if title == device_name]
        if len(matches) != 1:
            names = sorted({t for t, _ in rows.values()})
            sys.exit(f"Expected one device named '{device_name}', found {len(matches)}. "
                     f"Devices: {', '.join(names)}")
        key = matches[0]
        if rows[key][1] == profile_id:
            print(f"  '{device_name}' already uses '{PROFILE_NAME}'")
            return
        form = {k: prof for k, (_, prof) in rows.items() if prof}
        form[key] = profile_id
        self.apply("kidLis", **form)
        after = self.device_profiles()
        if after.get(key, (None, None))[1] != profile_id:  # Confirm that the TV's profile changed.
            sys.exit(f"FRITZ!Box: assigning '{PROFILE_NAME}' to '{device_name}' did not take. "
                     f"Check the router UI.")
        changed = [t for k, (t, p) in rows.items() if k in after and after[k][1] != p and t != device_name]
        if changed:
            print(f"  WARNING: other devices changed profile: {changed}")
        print(f"  '{device_name}' now uses '{PROFILE_NAME}'")


# ---------------------------------------------------------------- UniFi
# UniFi's content-filter API is undocumented. This code copies the calls the web UI makes, and
# the API has changed between UniFi OS versions. The code updates a Content Filter policy that
# you create once in the UI. If the result looks wrong, make the change in the UI as GUIDE.md
# describes.

class UniFi:
    def __init__(self, host, api_key, site="default"):
        self.base = f"https://{host}"
        self.site = site
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE  # UniFi gateways use a self-signed certificate.
        self.key = api_key
        print(f"UniFi: gateway {host}, site '{site}'. "
              "The API is unofficial, so check the UI afterward.")

    def _req(self, path, method="GET", body=None):
        headers = {"X-API-KEY": self.key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        raw = http(f"{self.base}{path}", method=method, json_body=body, headers=headers,
                   context=self.ctx, no_redirect=True)
        return json.loads(raw) if raw.strip() else {}

    def policies(self):
        data = self._req(f"/proxy/network/v2/api/site/{self.site}/content-filtering")
        return data.get("data", data) if isinstance(data, dict) else data

    def apply_block(self, policy_name, tv_mac):
        pols = self.policies()
        match = [p for p in pols if p.get("name") == policy_name]
        if len(match) != 1:  # Never guess. The wrong policy can filter unrelated clients.
            names = [p.get("name") for p in pols] or ["(none)"]
            sys.exit(f"Need exactly one Content Filter named '{policy_name}', found {len(match)}. "
                     f"Create or rename it in the UI (Settings > CyberSecure > Content Filter), "
                     f"scope it to the TV, then re-run. Existing policies: {names}")
        pol = match[0]
        pid = pol.get("_id") or pol.get("id")
        if not pid:
            sys.exit("UniFi: the matched policy has no id field, so your UniFi OS version uses "
                     "a different schema. Add the domains in the UI as GUIDE.md describes.")
        existing = [m.lower() for m in (pol.get("client_macs") or [])]
        others = [m for m in existing if not (tv_mac and m == tv_mac.lower())]
        if others:
            print(f"  WARNING: this policy already targets other clients: {', '.join(others)}. "
                  f"They will get this blocklist too.")
        block = pol.get("block_list") or []
        merged = block + [d for d in BLOCKLIST if d not in block]
        macs = existing + ([tv_mac.lower()] if tv_mac and tv_mac.lower() not in existing else [])
        body = dict(pol)
        body["block_list"] = merged
        body["client_macs"] = macs
        self._req(f"/proxy/network/v2/api/site/{self.site}/content-filtering/{pid}", "PUT", body)
        after = [p for p in self.policies() if (p.get("_id") or p.get("id")) == pid]  # read back
        verified = bool(after) and set(BLOCKLIST).issubset(set(after[0].get("block_list") or []))
        added = len(merged) - len(block)
        print(f"  Content Filter '{policy_name}': {len(block)} existing + {added} added "
              f"= {len(merged)} domains, scoped to {len(macs)} devices. "
              f"Read-back: {'OK' if verified else 'COULD NOT VERIFY, check the UI'}")


def _fritz_password(a):
    if a.fritz_password_file:
        return open(a.fritz_password_file).read().rstrip("\r\n")
    return getpass.getpass("FRITZ!Box password: ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tv", help="the TV's IP address")
    ap.add_argument("--keep", default=KEEP_DEFAULT, help=f"apps to leave running, default {KEEP_DEFAULT}")
    ap.add_argument("--fritz-device", help="the TV's name in FRITZ!Box > Internet > Filter")
    ap.add_argument("--list-fritz-devices", action="store_true",
                    help="log in and list FRITZ!Box device names, then exit")
    ap.add_argument("--fritz-host", default="fritz.box",
                    help="host name or IP address of the FRITZ!Box, default fritz.box")
    ap.add_argument("--fritz-user", help="defaults to the last user that logged in")
    ap.add_argument("--fritz-password-file", help="read the password from this file instead of asking for it")
    ap.add_argument("--unifi-host", help="IP address of the UniFi gateway, such as a UDM, UCG, UDR, or Express")
    ap.add_argument("--unifi-filter", default="Samsung TV",
                    help="name of the Content Filter policy to update, which you create in the UI first")
    ap.add_argument("--unifi-tv-mac", help="the TV's MAC address, to scope the filter to the TV only")
    ap.add_argument("--unifi-site", default="default",
                    help="UniFi site that holds the Content Filter policy, default 'default'")
    ap.add_argument("--unifi-key-file", help="read the UniFi API key from this file instead of asking for it")
    ap.add_argument("--print-blocklist", action="store_true",
                    help="print the blocklist for Pi-hole or AdGuard Home, then exit")
    a = ap.parse_args()

    if a.print_blocklist:
        print("\n".join(BLOCKLIST))
        return
    if a.list_fritz_devices:
        box = Fritz(a.fritz_host, a.fritz_user, _fritz_password(a))
        try:
            for name in sorted({t for t, _ in box.device_profiles().values()}):
                print(name)
        finally:
            box.logout()
        return
    if not (a.tv or a.fritz_device or a.unifi_host):
        ap.error("pass --tv, a router target such as --fritz-device or --unifi-host, or both")
    if a.tv:
        tv_cleanup(a.tv, set(a.keep.split(",")))
    if a.fritz_device:
        box = Fritz(a.fritz_host, a.fritz_user, _fritz_password(a))
        try:
            box.require_device(a.fritz_device)  # Check the name before writing the shared block list.
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
