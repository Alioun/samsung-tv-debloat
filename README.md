# Samsung Tizen TV cleanup

Debloat a Samsung TV: no home-screen ads, telemetry off, Samsung bloat removed, a launcher that
boots straight to your apps, more free RAM. Reversible. Works on most 2021–2025 TVs (Tizen 6–9).

## Start here

**[GUIDE.md](GUIDE.md)** — the full start-to-finish walkthrough: enable Developer Mode → root with
Apps2Samsung → debloat via the vetro dashboard → block ad/tracking domains on your router.

Most of the work is a one-click rooter (Apps2Samsung) plus on-screen toggles (vetro). The script
below is just the optional network-blocking layer.

## The script — `samsung_tv_cleanup.py`

Blocks Samsung's ad/tracking servers at your router and closes background bloat apps. Python 3.9+,
standard library only, nothing to install.

```
python3 samsung_tv_cleanup.py --tv <TV-IP>                               # close bloat apps
python3 samsung_tv_cleanup.py --fritz-device <TV name in FRITZ!Box>      # FRITZ!Box
python3 samsung_tv_cleanup.py --unifi-host <GW-IP> --unifi-tv-mac <MAC>  # UniFi
python3 samsung_tv_cleanup.py --print-blocklist                          # Pi-hole / AdGuard Home
```

- **FRITZ!Box:** adds the domains to Internet → Filter → Lists (keeping what's there), makes a
  "Samsung TV" access profile using them, and assigns it to the TV only. Prompts for the router
  password; doesn't store it. Run `--list-fritz-devices` to print the exact device names first.
  Delete any `--fritz-password-file` / `--unifi-key-file` after use (owner-only perms while it exists).
- **UniFi:** updates a Content Filter policy you create once in the UI, scoped to the TV's MAC.
  The UniFi API is unofficial — verify in the UI afterward. See GUIDE.md Step 4.
- **Pi-hole / AdGuard Home:** `--print-blocklist` and paste the output into your blocklist.

**Never block the bare `samsungqbe.com`, `samsungcloudsolution.com` or `.net`** — those host the
app store and firmware servers. The blocklist here is already narrowed to the safe ad subdomains.

Undo: vetro's Restore reverses the TV changes; remove the domains / access profile in your router.

## Credits

The root and on-TV debloat are powered by other projects — this repo adds the router blocklist
script and the written walkthrough:

- [vetro](https://github.com/andrearicci93/vetro) — on-TV launcher, debloater and dashboard
- [Apps2Samsung](https://github.com/Apps2Samsung/Apps2Samsung) — one-click installer/signer for the TV
- [chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root) — the root research
