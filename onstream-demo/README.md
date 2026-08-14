# OnStream Demo (Expo)

Mobile lab app to exercise OnStream: auth, VOD upload, signed HLS playback, live create (RTMP/WHIP/WHEP copy), live health, and revoke.

Engine docs: [`../docs/README.md`](../docs/README.md) · API map: [`../docs/API.md`](../docs/API.md).

## Why SDK 54 (not 57) for phones

Expo’s current docs note that during the **SDK 57 transition**, plain `create-expo-app@latest` still targets **SDK 54**, and **Expo Go on a physical device should use SDK 54**. SDK 57 needs a **development build** until Expo Go catches up.

This demo follows modern Expo patterns that carry forward to 57:

- Expo Router (file routes)
- `expo-video` + `contentType: 'hls'` (not deprecated `expo-av`)
- SecureStore session
- New Architecture enabled

To move to 57 later: `npx expo install expo@^57.0.0 --fix` and ship a dev client / APK.

## Security / npm audit

App source uses current Expo Router + `expo-video` (not deprecated `expo-av`).

`npm audit` findings are almost entirely **transitive Expo/Metro toolchain** deps, not demo app code.

Patched via `package.json` `overrides`: `postcss`, `uuid`, `js-yaml`, `nanoid`, `brace-expansion@5`.

**Remaining (cannot zero on SDK 54):** `image-size@<=2.0.2` has no fixed release yet; Metro pulls it, so `npm audit` still reports ~10 highs in that chain. Do **not** run `npm audit fix --force` — it jumps to Expo 57 and breaks Expo Go on phones. When `image-size` ships a patch (or you move to a SDK that drops it), re-run `npm audit`.

## Install

```bash
cd onstream-demo
npm install
```

Optional: pin versions with Expo:

```bash
npx expo install expo-video expo-secure-store expo-document-picker expo-clipboard expo-linear-gradient
```

## Run (Expo Go)

1. Start OnStream API on your PC (reachable on LAN).
2. In **Account** (or login), set API base to `http://<YOUR-LAN-IP>:8000` (not `localhost` on a phone).
3. Start the demo:

```bash
npm start
```

4. Scan the QR with **Expo Go** (same Wi‑Fi). Expo Go must be **SDK 54**.

If Android shows **`Failed to download remote update`**, see the reusable guide: [`docs/ANDROID_METRO_CONNECTION.md`](../docs/ANDROID_METRO_CONNECTION.md) (USB `adb reverse`, tunnel, LAN/firewall). Short version below.

**A — Tunnel (most reliable on locked Wi‑Fi)**

```powershell
# stop the current Metro (Ctrl+C), then:
npm run start:tunnel
```

Scan the new QR (uses Expo’s tunnel; needs internet on phone + PC). First run may install `@expo/ngrok`.

**B — USB + adb reverse** (device cable + USB debugging on)

```powershell
adb devices
adb reverse tcp:8081 tcp:8081
npm run start:usb
```

Then open the project from Expo Go (or press `a` in the Expo terminal).

**C — Fix LAN**

- PC and phone on the **same** Wi‑Fi (not guest / AP isolation).
- Windows Wi‑Fi profile = **Private** (Settings → Network → Wi‑Fi → properties).
- Allow **Node.js** through Windows Firewall (Private + Public), or allow inbound TCP **8081**.
- No VPN on phone/PC. If Expo shows a VirtualBox IP, force Wi‑Fi:

```powershell
$env:REACT_NATIVE_PACKAGER_HOSTNAME="192.168.1.2"
npm start
```

### Android emulator

`http://10.0.2.2:8000` reaches the host machine.

### iOS simulator

`http://localhost:8000` is fine.

## Features to test

| Screen | Exercises |
|--------|-----------|
| Sign in / register | `/v1/auth/*`, API base override, `/health` |
| VOD | list, multipart upload, status poll, playback token, HLS via `expo-video` |
| Live | create (copy stream key / RTMP / WHIP / WHEP once), health, token play, revoke. Phone camera is HTTPS `/demo/whip/` after the lab CA — not Expo Go. |
| Lab | Moderation, webhooks, browser upload/WHIP |
| Account | API URL, health ping, sign out |

## Env

```bash
# optional default (still overridable in-app)
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.10:8000
```

## Design

Cinema charcoal + signal teal, Syne + DM Sans — demo/lab UI, not App Store packaging.
