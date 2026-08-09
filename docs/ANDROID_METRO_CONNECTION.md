# Android: “Failed to download remote update”

**Error (Expo Go / Metro):**

```text
java.io.IOException: Failed to download remote update
```

This is a **device ↔ packager network** problem. The phone (or emulator) cannot download the JavaScript bundle from Metro on your PC. It is **not** usually a bug in your app source code.

Applies to:

- Expo Go + `npx expo start` / `npm start`
- React Native CLI + Metro (`npx react-native start`)
- Any project where the device loads a remote bundle from `exp://…` or `http://<pc-ip>:8081`

---

## Quick mental model

| Piece | Role |
|-------|------|
| Metro (packager) | Serves the JS bundle, usually on TCP **8081** |
| Expo Go / RN app | Must reach that port on your PC |
| LAN / USB / tunnel | How the phone finds Metro |

If that path is blocked (firewall, Wi‑Fi isolation, wrong IP, guest network, VPN), you get this error.

---

## Fix order (try top → bottom)

### 1) USB + `adb reverse` (best when the phone is cabled)

Works even when Wi‑Fi client isolation blocks LAN.

```powershell
adb devices
# expect: <serial>    device

adb reverse tcp:8081 tcp:8081
adb reverse --list
```

**Expo**

```powershell
npx expo start --localhost
# or: npm run start:usb   (if you added that script)
```

Then press `a`, or in Expo Go open: `exp://127.0.0.1:8081`.

**React Native (non-Expo)**

```powershell
adb reverse tcp:8081 tcp:8081
npx react-native start
npx react-native run-android
```

Re-run `adb reverse` after unplug/replug or some `adb kill-server` restarts.

---

### 2) Tunnel (best on locked / guest / corporate Wi‑Fi)

Bypasses local LAN by routing through Expo’s tunnel (needs internet on phone + PC).

```powershell
npx expo start --tunnel
# or: npm run start:tunnel
```

Scan the **new** QR code. First run may install `@expo/ngrok`.

---

### 3) Fix LAN (when you want Wi‑Fi QR scan)

1. Phone and PC on the **same** Wi‑Fi (not “Guest”, not phone-only hotspot unless the PC is joined to that hotspot).
2. Windows network profile = **Private**  
   Settings → Network & internet → Wi‑Fi → your network → **Private**.
3. Allow Metro through the firewall:
   - “Allow an app through Windows Firewall” → enable **Node.js** for Private (and Public if needed), **or**
   - Inbound allow TCP **8081** for the packager.
4. Turn off VPN on phone and PC while testing.
5. Confirm Metro’s advertised IP is your **Wi‑Fi** IPv4, not VirtualBox / Hyper-V / WSL virtual adapters:

```powershell
ipconfig
# Wireless LAN adapter Wi-Fi → IPv4 Address  (e.g. 192.168.1.2)
```

Force that host if Expo picks the wrong NIC:

```powershell
# PowerShell
$env:REACT_NATIVE_PACKAGER_HOSTNAME="192.168.1.2"
npx expo start
```

```bash
# bash / macOS / Linux
REACT_NATIVE_PACKAGER_HOSTNAME=192.168.1.2 npx expo start
```

Phone and QR should show `exp://192.168.1.2:8081` (your real LAN IP).

---

### 4) SDK / Expo Go mismatch

Expo Go’s SDK major must match the project (`expo` in `package.json`).

- Project SDK 54 → Expo Go build that supports **54**
- Upgrading the app to SDK 57 while Expo Go is still on 54 (or the reverse) often fails to load

Check: project `package.json` → `"expo": "~54.x"` vs Expo Go’s listed SDK.

---

## Optional `package.json` scripts (Expo)

```json
{
  "scripts": {
    "start": "expo start",
    "start:tunnel": "expo start --tunnel",
    "start:usb": "expo start --localhost"
  }
}
```

---

## Checklist

- [ ] `adb devices` shows `device` (for USB path)
- [ ] `adb reverse tcp:8081 tcp:8081` applied
- [ ] Metro actually listening (`http://127.0.0.1:8081/status` → `packager-status:running`)
- [ ] Same Wi‑Fi / Private profile / no VPN (for LAN path)
- [ ] Firewall allows Node.js or TCP 8081
- [ ] Packager hostname = Wi‑Fi IPv4, not a VM adapter
- [ ] Expo Go SDK matches project SDK
- [ ] Tunnel works as fallback (`expo start --tunnel`)

---

## What this does *not* fix

- Crashes **after** the app loads (redbox / JS exceptions) — those are app bugs
- API calls to `localhost` on a physical phone — use your PC LAN IP (e.g. `http://192.168.1.2:8000`) for backend URLs
- Missing cleartext HTTP for **custom native builds** — that is `usesCleartextTraffic` / ATS; Expo Go already allows Metro over HTTP

---

## One-liner summary

**Phone can’t reach Metro on `:8081` → use USB `adb reverse`, or `--tunnel`, or fix LAN/firewall/IP.**
