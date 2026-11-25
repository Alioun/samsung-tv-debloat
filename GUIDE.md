# Debloat a Samsung Tizen TV and remove its ads

When you finish, the home screen shows no ads, telemetry and ACR are off, and Samsung's bloat apps
are gone. ACR is the feature that identifies what you watch. A replacement launcher boots straight
to your apps, and the TV has more free RAM, so the UI responds faster. You can undo most changes,
with the exceptions listed in the next section. Read that section before you start.

You need the TV's IP address, a computer on the same network, and a phone with the **SmartThings**
app.

---

## Check compatibility and risks before you start

- **Check that your TV can be rooted.** The root works on **Tizen 6 to 9**, which covers most
  Samsung TVs from 2021 to 2025. To see your version, open **Settings > Support > About This TV**.
  **A Tizen 10 TV from 2026 can't be rooted.** On those TVs, do only the DNS block in Step 4. The
  author tested every step on a 2022 S95B with Tizen 6.5 and firmware 1720.
- **A firmware update can remove root for good.** One report describes a 2022 TV that lost root
  to a forced update, with no way to get it back. Before you root, plan to turn off auto-update in
  Step 3. Decide whether you accept the trade-off: **without updates, the TV gets no security
  fixes.**
- **Some changes are hard to undo.** When you disable a package in vetro, Restore brings it back.
  When you **uninstall** a package, that is not always true. Some apps then need a reinstall from
  the store or a factory reset, and a few settings need manual recovery. **Prefer Disable over
  Uninstall.** Don't remove an app unless you know how to get it back.

---

## Step 1. Turn on Developer Mode on the TV

1. **Sign in to your Samsung account** on the TV first, under **Menu > Settings > Account**.
   Without the sign-in, the TV often ignores the code in step 3.
2. Open **Smart Hub > Apps**. Newer firmware has no separate Apps menu. On those TVs, open the Apps
   grid, scroll to the **bottom**, and open **App Settings**.
3. Enter **`1 2 3 4 5`**. If your remote has no number buttons, use the **virtual keypad in the
   SmartThings app**. To reach it, add the TV in SmartThings, open its remote, and open the keypad.
   Type fast. If nothing happens, press `5` two or three more times. A USB keyboard plugged into
   the TV also works.
4. In the popup, set **Developer mode** to **On**. For **Host PC IP**, enter your **computer's**
   local IP address, such as `192.168.1.50`. Compare the octets with your router's IP address. A
   transposed IP address is the most common reason the next step fails.
5. Select **OK**, then **restart the TV**. The Developer Mode connection starts only after a reboot.

---

## Step 2. Root the TV from your computer

**Apps2Samsung** roots the TV in one click. It creates the Samsung certificate, signs the app, and
installs it for you.

1. Install Apps2Samsung. On Windows, run `winget install Apps2Samsung.Apps2Samsung`. On macOS or
   Linux, download the build from <https://github.com/Apps2Samsung/Apps2Samsung/releases>.
2. Open Apps2Samsung. It finds the TV on its own. On the first run, it signs you in to Samsung once
   to create a signing certificate, which it reuses later. If it can't connect, go back to Step 1
   and fix the Host PC IP.
3. In the catalog, find **vetro**, which is marked `(root)`. Install it. Apps2Samsung asks you to
   confirm with `--allow-root`. That confirmation is there on purpose.
4. On the TV, **open vetro once**. If vetro asks for a Host PC IP, set it to `127.0.0.1` and
   **restart the TV**. vetro then roots the TV by itself in about 20 seconds, and you no longer need
   the computer.

---

## Step 3. Debloat the TV in the vetro dashboard

Open **`http://<TV-IP>:8099`** in a browser on your network. vetro shows the exact address on the
TV. Restore reverses a **Disable**, but not always an **Uninstall**, as the risks section explains.
Prefer Disable, and keep the dashboard tab open so you can switch anything back at once.

**Turn off auto-update first, because a forced firmware update can remove root for good:**

- In vetro's **Disable** area, turn off the software auto-updater, `swu-auto-upgrade`.
- On the TV, open **Settings > Support > Software Update > Auto Update** and set it to **Off**.

**Turn off telemetry in the Privacy & ads tab.** Disable these packages:

- Viewing information and ACR: `com.samsung.tv.acr`
- Interest-based ads: `adplatform.ADPlayer` and `targeted-ad-service`
- Analytics: `samsung-analytics`, `pisa-service`, and `com.samsung.tv.cis`

On **2022** models, also disable **`com.samsung.tv.iacr`** and
**`com.samsung.tv.screen-analysis-dbmgr`**. The catalog may not flag these two packages.

**Free RAM with Disable.** Samsung TV Plus and Art or Ambient mode free the most. HbbTV, Vision AI,
and Bixby voice also take RAM. **Disable** these apps, which Restore fully reverses. **Uninstall**
an app only if you don't use it and know how to reinstall it. Keep your streaming apps.

**Set the launcher.** Point vetro's replacement launcher at the apps you use, so the TV skips
Samsung Home.

**Leave core packages alone.** Don't touch any package named `org.tizen.*` or a core
`com.samsung.*` package, and leave `org.tizen.netflixlowmem` in place. vetro guards the dangerous
packages. If vetro refuses a change, leave that package. Skip vetro's Shards unless you know what a
given Shard does. A Shard is a root plugin that runs outside the sandbox.

Restart the TV after the big removals.

---

## Step 4. Block Samsung's ad and tracking servers on your network

The network block is a second layer. It still works if a firmware update turns a disabled package
back on. The block uses `samsung_tv_cleanup.py`, which needs Python 3.9 or later and only the
standard library.

### UniFi

1. In the UniFi UI, open **Settings > CyberSecure > Content Filter** and create a policy. Name it
   `Samsung TV` and scope it to the TV by client device or MAC address.
2. Create an API key under **Settings > Control Plane > API Keys**.
3. Run the script to add the block domains to that policy. It asks for the API key.
   ```
   python3 samsung_tv_cleanup.py --unifi-host <GATEWAY-IP> \
       --unifi-filter "Samsung TV" --unifi-tv-mac <TV-MAC>
   ```
   UniFi's content-filter API is unofficial and changes between UniFi OS versions. **Check in the
   UI that the domains arrived.** If the script can't match the policy, run `--print-blocklist` and
   paste the domains into the policy's block list by hand.

### FRITZ!Box

```
python3 samsung_tv_cleanup.py --fritz-device <TV name in FRITZ!Box>
```

The script adds the domains to **Internet > Filter > Lists**. It creates a "Samsung TV" access
profile that uses them and assigns the profile to the TV only. It asks for the router password and
doesn't store it.

### Pi-hole or AdGuard Home

```
python3 samsung_tv_cleanup.py --print-blocklist
```

Add the output to your blocklist.

**Block only these domains.** Never block the bare `samsungqbe.com`, `samsungcloudsolution.com`, or
`samsungcloudsolution.net`. Those domains host the app store and the firmware servers. When they
are blocked, the Apps panel fails with "server isn't available."

---

## Troubleshooting

- **The Apps panel says "Server isn't available."** You or a blocklist blocked the app store
  backend. Make sure that the TV can reach `osb.samsungqbe.com` and the `samsungcloudsolution`
  domains, and block only the ad subdomains listed above. Then unplug the TV for 30 to 60 seconds
  to clear its DNS cache.
- **`12345` does nothing.** Sign in to your Samsung account first. Enter the code in **App
  Settings**, not in the main **Settings**. Type fast, or try a USB keyboard.
- **Apps2Samsung can't connect.** The Host PC IP in Developer Mode is wrong, often by a transposed
  octet, or the TV wasn't restarted after you turned on Developer Mode. Fix the IP address and
  restart the TV.
- **You want to undo everything.** Use vetro's Restore to bring the packages back. Remove the DNS
  block from your router, and turn off Developer Mode.

---

## Credits

Other people wrote the root and the debloat on the TV. This repo adds only the router blocklist
script and this guide.

- **[vetro](https://github.com/andrearicci93/vetro)** is the launcher, debloater, and dashboard
  that does all the work on the TV.
- **[Apps2Samsung](https://github.com/Apps2Samsung/Apps2Samsung)** is the one-click installer and
  signer that puts vetro on the TV.
- **[chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root)** published
  the root research that vetro builds on.

Each project has its own instructions and license. Follow those, because they can change
independently of this guide.
