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
2. In **Lab** / login, set API base to `http://<YOUR-LAN-IP>:8000` (not `localhost` on a phone).
3. Start the demo:

```bash
npm start
```

4. Scan the QR with **Expo Go** (same Wi‑Fi).

### Android emulator

`http://10.0.2.2:8000` reaches the host machine.

### iOS simulator

`http://localhost:8000` is fine.

## Features to test

| Screen | Exercises |
|--------|-----------|
| Sign in / register | `/v1/auth/*`, API base override, `/health` |
| VOD | list, multipart upload, status poll, playback token, HLS via `expo-video` |
| Live | create (copy stream key / RTMP / WHIP / WHEP once), health, token play, revoke |
| Lab | API URL, health ping, sign out |

## Env

```bash
# optional default (still overridable in-app)
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.10:8000
```

## Design

Cinema charcoal + signal teal, Syne + DM Sans — demo/lab UI, not App Store packaging.
