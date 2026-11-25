# Samsung Tizen TV — debloat & de-ad, start to finish

End result: no home-screen ads, telemetry/ACR off, Samsung bloat gone, a launcher that boots
straight to your apps, and more free RAM so the UI isn't sluggish. Most changes are reversible
(see the caveats below) — but read "Before you start" first.

You need: the TV's IP, a computer on the same network, and a phone with the **SmartThings** app.

---

## Before you start — compatibility & risks (read this)

- **Check your TV is rootable.** This works on **Tizen 6–9** (most 2021–2025 Samsung TVs). Confirm
  on the TV under Settings → Support → About This TV. **Tizen 10 (2026) can't be rooted** — on
  those, do only the DNS block (Step 4). Tested end-to-end on a 2022 S95B (Tizen 6.5, firmware 1720).
- **A firmware update can permanently remove root** — there are reports of a 2022 TV losing root to
  a forced update, with no way back. Before you root, plan to turn auto-update **off** (Step 3) and
  understand the trade-off: **no updates also means no security fixes**. Decide if you're OK with that.
- **Not everything un-does cleanly.** Disabling a package via vetro is reversible; **uninstalling**
  one is not always — some apps need a reinstall (from the store or a factory reset) and a few
  settings need manual recovery. **Prefer Disable over Uninstall**, and don't remove an app unless
  you know how to get it back.

---

## Step 1 — Enable Developer Mode (on the TV)

1. **Sign into your Samsung account** on the TV first (Menu → Settings → account) — the code below
   often won't register otherwise.
2. Open **Smart Hub → Apps**. On newer firmware there's no standalone Apps menu — open the Apps
   grid, scroll to the **bottom**, and open **App Settings**.
3. Enter **`1 2 3 4 5`**. If your remote has no number buttons, use the **SmartThings app's virtual
   keypad** (add the TV in SmartThings → open its remote → keypad). Type fast; if nothing happens,
   press `5` a couple more times. A USB keyboard plugged into the TV also works.
4. In the popup: **Developer mode → On**. For **Host PC IP**, enter your **computer's** local IP
   (e.g. `192.168.1.50`). Double-check the octet order against your router's IP — a transposed IP
   is the #1 reason this fails later.
5. **OK**, then **restart the TV**. Developer Mode's connection only comes up after a reboot.

---

## Step 2 — Root the TV (one-click, from your computer)

The root step is done by **Apps2Samsung**, which handles the Samsung certificate, signing and
install for you.

1. Install Apps2Samsung: Windows `winget install Apps2Samsung.Apps2Samsung`, or get the
   mac/Linux build from <https://github.com/Apps2Samsung/Apps2Samsung/releases>.
2. Open it. It should auto-detect the TV. First run signs you into Samsung once to make a signing
   certificate (reused after). If it can't connect, Step 1 isn't right — fix the Host PC IP.
3. In the catalog, find **vetro** (marked `(root)`). Install it — it asks for an `--allow-root`
   confirmation; that gate is deliberate.
4. On the TV, **open vetro once**. If it asks, set its Host PC IP to `127.0.0.1` and **restart the
   TV**. It then self-roots (~20s, no computer needed afterward).

---

## Step 3 — Debloat ([vetro](https://github.com/andrearicci93/vetro) dashboard, from any browser)

Open **`http://<TV-IP>:8099`** in a browser on your network (vetro shows the exact address on the
TV). **Disable** actions are reversible via Restore; **Uninstall** is not always (see "Before you
start"). Favour Disable, and keep this tab open so you can flip anything back immediately.

**Do this FIRST — lock auto-update (protects your root):**
- In vetro's **Disable** area, turn off the software auto-updater (`swu-auto-upgrade`).
- On the TV: **Settings → Support → Software Update → Auto Update → Off**.
- A forced firmware update can permanently remove root. Don't skip this.

**Kill telemetry (Privacy & ads tab):** viewing info / ACR (`com.samsung.tv.acr`), interest-based
ads (`adplatform.ADPlayer`, `targeted-ad-service`), analytics (`samsung-analytics`, `pisa-service`,
`com.samsung.tv.cis`). On **2022** sets also disable **`com.samsung.tv.iacr`** and
**`com.samsung.tv.screen-analysis-dbmgr`** — the catalog may not flag these automatically.

**Free RAM (prefer Disable):** Samsung TV Plus and Art/Ambient mode (biggest wins), HbbTV,
Vision AI, Bixby/voice — **Disable** these; it's fully reversible. Only **Uninstall** an app if you
don't use it *and* know how to reinstall it (keep your streaming apps).

**Launcher:** point vetro's replacement launcher at the apps you actually use, so the TV skips
Samsung Home.

**Don't touch:** anything named `org.tizen.*` or core `com.samsung.*`, and `org.tizen.netflixlowmem`.
vetro guards the dangerous ones — if it refuses, leave it. Skip "Shards" (unsandboxed root plugins)
unless you know what one does.

Restart the TV after the big removals to feel the difference.

---

## Step 4 — Block Samsung ad/tracking servers on your network

A second layer that also helps if a firmware update ever re-enables something. Uses
`samsung_tv_cleanup.py` (Python 3.9+, stdlib only).

### UniFi
1. In the UI: **Settings → CyberSecure → Content Filter → create a policy** (e.g. name it
   `Samsung TV`), and scope it to the TV (by client device / MAC).
2. Make an API key: **Settings → Control Plane → API Keys**.
3. Add the block domains to that policy:
   ```
   python3 samsung_tv_cleanup.py --unifi-host <GATEWAY-IP> \
       --unifi-filter "Samsung TV" --unifi-tv-mac <TV-MAC>
   ```
   (It prompts for the API key.) UniFi's content-filter API is unofficial and varies by UniFi OS
   version — **verify the domains landed in the UI afterward**. If the script can't match the
   policy, just paste the domains from `--print-blocklist` into the policy's block list by hand.

### FRITZ!Box
```
python3 samsung_tv_cleanup.py --fritz-device <TV name in FRITZ!Box>
```
Adds the domains to Internet → Filter → Lists, makes a "Samsung TV" access profile using them, and
assigns it to the TV only. Prompts for the router password; doesn't store it.

### Pi-hole / AdGuard Home
```
python3 samsung_tv_cleanup.py --print-blocklist
```
Add the output to your blocklist.

**Important:** block only these specific domains. Never block the bare `samsungqbe.com`,
`samsungcloudsolution.com` or `.net` — those host the app store and firmware servers, and blocking
them makes the Apps panel fail with "server isn't available."

---

## Troubleshooting

- **"Server isn't available" in the Apps panel** → you (or a blocklist) blocked the app-store
  backend. Make sure `osb.samsungqbe.com` / `*.samsungcloudsolution.*` are reachable; block only
  the specific ad subdomains above. Power-cycle the TV (unplug 30–60s) to clear its DNS cache.
- **`12345` does nothing** → sign into your Samsung account first; enter it from **App Settings**,
  not the main Settings; type fast; try a USB keyboard.
- **Apps2Samsung won't connect** → Developer Mode Host PC IP is wrong (often a transposed octet) or
  the TV wasn't restarted after enabling it. Fix and reboot.
- **Undo everything** → vetro's Restore puts packages back; remove the DNS block in your router;
  turn Developer Mode off.

---

## Credits

The root and on-TV debloat are other people's work — this repo only adds the router-side blocklist
script and this walkthrough:

- **[vetro](https://github.com/andrearicci93/vetro)** — the launcher, debloater and dashboard that
  does all the on-TV work.
- **[Apps2Samsung](https://github.com/Apps2Samsung/Apps2Samsung)** — the one-click installer/signer
  that gets vetro onto the TV.
- **[chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root)** — the root
  research vetro builds on.

Follow each project's own instructions and licenses; they can change independently of this guide.
