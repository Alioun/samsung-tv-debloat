# Samsung Tizen TV cleanup

This repo debloats a Samsung TV. When you finish, the home screen shows no ads, telemetry is off,
and Samsung's bloat apps are gone. A replacement launcher boots straight to your apps, and the TV
has more free RAM. You can undo each change. It works on most Samsung TVs from 2021 to 2025, which
run Tizen 6 to 9.

## Start here

[The start-to-finish guide](GUIDE.md) walks through four steps:

1. Turn on Developer Mode on the TV.
2. Root the TV with Apps2Samsung.
3. Debloat the TV in the vetro dashboard.
4. Block Samsung's ad and tracking domains on your router.

Apps2Samsung roots the TV in one click, and vetro does the debloat with on-screen switches. The
script below is the optional fourth step, which blocks the TV's traffic at the network.

## The `samsung_tv_cleanup.py` script

The script blocks Samsung's ad and tracking servers at your router and closes bloat apps that run
in the background. It needs Python 3.9 or later and uses only the standard library, so you install
nothing.

```
python3 samsung_tv_cleanup.py --tv <TV-IP>                               # close bloat apps
python3 samsung_tv_cleanup.py --fritz-device <TV name in FRITZ!Box>      # FRITZ!Box
python3 samsung_tv_cleanup.py --unifi-host <GW-IP> --unifi-tv-mac <MAC>  # UniFi
python3 samsung_tv_cleanup.py --print-blocklist                          # Pi-hole or AdGuard Home
```

- **FRITZ!Box.** The script adds the domains to **Internet > Filter > Lists** and keeps the entries
  already there. It creates a "Samsung TV" access profile that uses the list and assigns the
  profile to the TV only. It asks for the router password and doesn't store it. To see the exact
  device names first, run `--list-fritz-devices`.
- **UniFi.** You create a Content Filter policy once in the UniFi UI. The script then updates that
  policy and scopes it to the TV's MAC address. The UniFi API is unofficial, so check the policy in
  the UI afterward. Step 4 of [the guide](GUIDE.md) has the details.
- **Pi-hole or AdGuard Home.** Run `--print-blocklist` and paste the output into your blocklist.

If you pass `--fritz-password-file` or `--unifi-key-file`, delete that file after the run. Only
your user account should be able to read it while it exists.

**Never block the bare `samsungqbe.com`, `samsungcloudsolution.com`, or `samsungcloudsolution.net`.**
Those domains host the app store and the firmware servers. The blocklist in this repo already
contains only the ad subdomains that are safe to block.

To undo everything, use vetro's **Restore** for the TV changes. Then remove the domains and the
access profile from your router.

## Credits

Other projects do the root and the debloat on the TV. This repo adds the router blocklist script
and the written guide.

- [vetro](https://github.com/andrearicci93/vetro) is the launcher, debloater, and dashboard on the TV.
- [Apps2Samsung](https://github.com/Apps2Samsung/Apps2Samsung) installs and signs apps for the TV in one click.
- [chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root) published the root research.
