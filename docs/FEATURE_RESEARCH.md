# OnStream — feature research brief

**Date:** 2026-08-13  
**Purpose:** Survey open-source projects, reference systems, and industry writing for *new feature ideas* — not a commitment to build them. Use this with [`TODO.md`](../TODO.md) (local) and existing design docs.

**OnStream today (context):** Self-hosted `/v1` video API + Expo lab; MediaMTX for live (WHIP/WHEP already in the stack); ABR HLS VOD; captions/chapters/moderation/FTS; engagement (continue/history/saved/shares); playlists/API keys exist on API but not fully in Expo UI.

---

## How to use this doc

1. Skim **§A** (projects you named) and **§B** (extra research).
2. Use **§C** (articles) for protocol/product framing.
3. Decide from **§D** (opportunity matrix) what to pull into TODO next.
4. Prefer *product slices that leverage what we already ship* over greenfield media servers.

---

## A. Projects you linked

### 1. [pingostack/pingos](https://github.com/pingostack/pingos) (~1k★)

| | |
|--|--|
| **What** | Nginx-based live media server (extends nginx-rtmp): RTMP, HTTP-FLV, HTTP-TS, HLS / HLS+, DASH, H.264/H.265, AAC/MP3 |
| **Also** | Live recording (FLV/TS), GOP cache for fast start, dynamic config, HTTP control API, notify hooks, multi-process / cluster push-pull, companion [pingos-player](https://github.com/pingostack/pingos-player) |
| **Relevance to OnStream** | Protocol breadth + **live DVR/recording** + **HTTP notify** patterns. We already use MediaMTX rather than nginx-rtmp; treat PingOS as a *feature checklist*, not a drop-in replacement. |
| **Ideas to steal** | Live → VOD archive on end; richer ingest notify → webhooks; HTTP-FLV / low-buffer web preview; multi-protocol playback URLs per stream; console/stats page for ops |

### 2. [streamlinevideo/streamline](https://github.com/streamlinevideo/streamline) (~780★)

| | |
|--|--|
| **What** | Educational **reference design** for E2E live: capture → encode → package → uplink → origin → CDN → player (FFmpeg, commodity GPU/DeckLink, Caddy origin, AWS CDN notes, hls.js) |
| **Also** | Sibling [low-latency-preview](https://github.com/streamlinevideo/low-latency-preview) (OSS LL-DASH PoC) |
| **Relevance** | Architecture storytelling and lab ops — mirrors our `scripts/live_lab_publish.py` + MediaMTX + `/demo/` path |
| **Ideas to steal** | Documented **glass-to-glass pipeline diagram** in README; encoder appliance profile; CDN-oriented segment lifecycle (PUT/DELETE); white-label player page uploaded with stream; contribution vs distribution split |

Site: [streamlinevideo.github.io/streamline](https://streamlinevideo.github.io/streamline/)

### 3. [shiyiya/oplayer](https://github.com/shiyiya/oplayer)

| | |
|--|--|
| **What** | Modular HTML5 player (vanilla JS): HLS / DASH / FLV / mpegts / WebTorrent plugins, captions, PiP, Chromecast, AirPlay, playlist UI, danmaku, **seek thumbnails** (sprite/VTT), i18n, DRM hooks |
| **Docs** | [oplayer.vercel.app/docs](https://oplayer.vercel.app/docs/) |
| **Relevance** | Player UX gap vs our Expo `HlsPlayer` + thin `/demo/` hls.js — browser player polish, not core API |
| **Ideas to steal** | Storyboard / scrub-preview thumbnails; multi-track captions UI; quality / audio / subtitle defaults; Chromecast/AirPlay; playlist side panel; keyboard shortcuts; optional danmaku for live chat overlay experiments |

---

## B. Additional open-source research

### Live / media servers (MediaMTX peers)

| Project | Link | Why it matters for OnStream |
|---------|------|-----------------------------|
| **MediaMTX** | [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx) | *Already in stack.* Baseline for WHIP/WHEP/RTSP/HLS. Compare feature velocity to peers below. |
| **SRS** | [ossrs/srs](https://github.com/ossrs/srs) | Mature RTMP/WebRTC/HLS/HTTP-FLV/SRT/DASH; WHIP/WHEP; clustering; Prometheus. Ideas: protocol bridge matrix, HTTP API ergonomics, DVR. |
| **OvenMediaEngine** | [OvenMediaLabs/OvenMediaEngine](https://github.com/OvenMediaLabs/OvenMediaEngine) | Sub-second WebRTC + **LL-HLS**, embedded ABR transcoder, WHIP simulcast, SRT, recording, OvenPlayer + OvenLiveKit. Ideas: LL-HLS path, scheduled/pre-recorded channels, multiplex tracks. |
| **LiveForge** | [im-pingo/liveforge](https://github.com/im-pingo/liveforge) | Go multi-protocol (incl. LL-HLS partials, WHIP/WHEP, HTTP-FLV, web console). Ideas: LL-HLS feature flags, built-in WHIP publish console (lab). |
| **Owncast** | [owncast/owncast](https://github.com/owncast/owncast) | “Twitch-in-a-box”: RTMP ingest + HLS + **first-class chat**, followers, webhooks, embed. Ideas: live chat, streamer profile page, follower notifications, embeddable player. |

### VOD / platform (PeerTube-class)

| Project | Link | Why it matters |
|---------|------|----------------|
| **PeerTube** | [Chocobozzz/PeerTube](https://github.com/Chocobozzz/PeerTube) | Channels, federation (ActivityPub), P2P browser delivery, live+VOD archive, embeds, follows/RSS. Ideas: **channels/orgs**, follows, federation (long-term), live→VOD. |
| **MediaCMS** | [mediacms-io/mediacms](https://github.com/mediacms-io/mediacms) | Django/React media CMS: playlists, comments, likes, RBAC, categories/tags, trimmer, Whisper captions, LTI/LMS, public/unlisted/private. Closest “product CMS” checklist for our API gaps. |
| **Tube** | (awesome-selfhosted listings) | Lightweight Go YouTube-like: collections, RSS, auto-transcode. Ideas: collections UX, RSS feeds. |

Comparative read: [Owncast vs PeerTube vs nginx-rtmp](https://sumguy.com/owncast-vs-peertube-vs-nginx-rtmp/)

### Players & toolkits

| Project | Link | Ideas |
|---------|------|-------|
| **OvenPlayer** | [OvenMediaLabs/OvenPlayer](https://github.com/OvenMediaLabs/OvenPlayer) | WebRTC + LL-HLS player paired with OME |
| **OvenLiveKit** | [OvenLiveKit-Web](https://github.com/OvenMediaLabs/OvenLiveKit-Web) | Browser encoder for WHIP-style publish → maps to TODO **#3 In-app WHIP** |
| **Eyevinn WHIP toolkit** | (referenced widely in WHIP articles) | Open WHIP/WHEP client/server PoCs for lab |
| **video.js / hls.js / dash.js** | ecosystem standards | Scrub previews, quality menus, accessibility |

### Labs / lists

- [awesome-selfhosted — Video Streaming](https://awesome-selfhosted.net/tags/media-streaming---video-streaming.html)
- CyTube / SyncTube — synchronized watch + chat (social viewing angle)

---

## C. Articles & industry writing (Medium / Substack / vendor blogs)

| Source | Link | Takeaways for OnStream |
|--------|------|------------------------|
| **Mux — LL live guide** | [LL-HLS, WebRTC, CMAF](https://www.mux.com/articles/low-latency-live-streaming-developers-guide-ll-hls-webrtc-cmaf) | Default mass live = **LL-HLS (~2–4s)**; WebRTC when sub-second interaction is required; CMAF when dual HLS+DASH from one encode. |
| **Fora Soft — latency 2026** | [Sub-second at scale](https://www.forasoft.com/blog/article/minimizing-latency-to-less-than-1-sec-for-mass-streams-315) | Protocol ladder: WebRTC / MoQ / WHIP-WHEP / SRT / LL-HLS / classic HLS. Hybrid: interactive tier + CDN LL-HLS fan-out. |
| **Fora Soft — WHIP/WHEP** | [Replace RTMP](https://www.forasoft.com/blog/article/whip-whep-replace-rtmp-live-streaming-2026) | WHIP = RFC 9725 (Mar 2025); OBS 30+ native; industry checklist. We already expose WHIP — double down on **dev-client publish UX** and WHEP playback polish. |
| **Mux — instant clips** | [Create instant clips](https://www.mux.com/docs/guides/create-instant-clips) | Clip via playback URL time windows (no re-encode) + storyboard params — product pattern for “highlight from live/VOD”. |
| **Cloudflare — Media Transformations** | [Blog](https://blog.cloudflare.com/media-transformations-for-video-open-beta/) | On-the-fly clip / frame / **spritesheet** for seek previews. |
| **Cloudflare Stream changelog** | [Docs](https://developers.cloudflare.com/stream/changelog/) | Player seek thumbnails, PiP, WHIP/WHEP upgrades, clip API — UX bar for commercial players. |
| **SumGuy** | [Owncast vs PeerTube](https://sumguy.com/owncast-vs-peertube-vs-nginx-rtmp/) | Positioning: Owncast = live+chat; PeerTube = archive+federation; nginx-rtmp = plumbing. OnStream sits closer to “plumbing + product API” (custom). |

*(Substack/Medium often remix Mux/Cloudflare/WHIP themes; prioritize primary specs and vendor engineering posts above listicles.)*

---

## D. Opportunity matrix → OnStream

Legend: **Have** / **Partial** / **Gap**. Priority = fit for *next* work given current TODO.

| Idea | Source(s) | Status | Suggested priority | Notes |
|------|-----------|--------|--------------------|-------|
| Channels / orgs / multi-user ownership | PeerTube, MediaCMS, TODO #1 | Gap | **Last** | PeerTube/MediaCMS pattern; unlocks multi-user. New tenancy model — **build last** |
| Comments / likes / reactions | MediaCMS, Owncast, TODO #2 | Gap | High (TODO #2) | Engagement next to favorites |
| In-app WHIP publish (dev client) | OvenLiveKit, WHIP articles, TODO #3 | Partial (URL + MediaMTX) | **Last** | Industry WHIP RFC wave; Expo Go cannot encode — **build last** (keep `/demo/whip/`) |
| Semantic search UI toggle | TODO #4 | **Shipped** | Medium | Keyword / semantic; capabilities + dim-mismatch skip; mock labeled as lab |
| Playlists Expo UI | MediaCMS, OPlayer, TODO #9 | **Shipped** | High (TODO #9) | Library + playlist screens |
| API keys Expo UI | TODO #10 | **Shipped** | Medium | Scopes enforced; JWT-only key admin; last_used throttled |
| All my share links screen | TODO #8 | **Shipped** | Medium | Lab + Library inbox: audit/revoke; tokens still once-at-create |
| Live chat | Owncast, CyTube | Gap | Medium | Distinct live product slice |
| Live → VOD / DVR archive | PingOS, PeerTube, OME | **Shipped** (EVENT DVR while live + revoke → READY VOD) | High | Mid-stream scrub on the archive playlist |
| LL-HLS delivery | Mux, OME, LiveForge | Gap | Medium–High | Latency product story |
| Scrub / storyboard previews | OPlayer, CF Stream, Mux | **Shipped** (`/demo/` quality + keyboard + DVR-safe hover; sprite after VOD transcode or live-archive job; Expo filmstrip) | Medium | Live DVR hover does not invent a mid-stream sprite |
| Instant / clip highlights | Mux clips, CF transforms | Gap | Medium | Builds on chapters + share |
| Video trimmer | MediaCMS | Gap | Low–Medium | Editing slice |
| Chromecast / AirPlay | OPlayer, CF player | Gap | Low | Player polish |
| Danmaku / live overlay comments | OPlayer | Gap | Low | Fun, not core |
| Federation (ActivityPub) | PeerTube, Owncast | Gap | Low (long-term) | Heavy product bet |
| HTTP-FLV / multi-protocol play URLs | PingOS, SRS | Gap | Low | MediaMTX may already cover enough |
| Origin–edge / cluster docs | Streamline, SRS, PingOS | Partial (Compose) | Low | Ops docs slice |
| QoE / Mux-like analytics | Mux Data articles | Partial (metrics exist) | Medium | Viewer QoE dashboard |
| Scheduled / 24-7 channel | OME | Gap | Low | Niche live |
| Embeddable player + oEmbed | PeerTube, Owncast | **Shipped** (`GET /v1/oembed` spec JSON; `/demo/watch/?v=` + share peek; embed click-to-play) | Medium | Creator distribution |
| RBAC categories | MediaCMS | Gap | Medium | With channels/orgs |
| Unlisted visibility | MediaCMS | Partial (`is_public`) | Easy win | Third state: unlisted |
| RSS / Atom feeds | PeerTube, Tube | Gap | Easy win | Per-channel or user library |

---

## E. Suggested “today / this week” shortlist

If picking **one** research-backed slice after the merge:

1. **Playlists UI + polish** — shipped (Library + playlist screens).  
2. **Channels / orgs / multi-user ownership** — PeerTube/MediaCMS pattern; unlocks multi-user (TODO #1). **Build last** (new tenancy model).  
3. **Live → VOD archive** — shipped (DVR while live + revoke promote).  
4. **In-app WHIP publish (dev client)** — industry WHIP RFC wave; TODO #3. **Build last** (Expo Go cannot encode; keep `/demo/whip/`).  
5. **Player scrub previews + `/demo/` upgrade** — shipped (quality, keyboard, honest DVR thumbs; sprite after transcode/promote).

Defer for later: federation, danmaku, full DRM, MoQ (watch space, don’t build yet).

---

## F. Source index (quick links)

**You named**

- https://github.com/pingostack/pingos  
- https://github.com/streamlinevideo/streamline  
- https://github.com/shiyiya/oplayer  

**Also researched**

- https://github.com/bluenviron/mediamtx  
- https://github.com/ossrs/srs  
- https://github.com/OvenMediaLabs/OvenMediaEngine  
- https://github.com/im-pingo/liveforge  
- https://github.com/owncast/owncast  
- https://github.com/Chocobozzz/PeerTube  
- https://github.com/mediacms-io/mediacms  
- https://github.com/OvenMediaLabs/OvenPlayer  
- https://github.com/OvenMediaLabs/OvenLiveKit-Web  
- https://awesome-selfhosted.net/tags/media-streaming---video-streaming.html  
- https://www.mux.com/articles/low-latency-live-streaming-developers-guide-ll-hls-webrtc-cmaf  
- https://www.forasoft.com/blog/article/whip-whep-replace-rtmp-live-streaming-2026  
- https://www.forasoft.com/blog/article/minimizing-latency-to-less-than-1-sec-for-mass-streams-315  
- https://www.mux.com/docs/guides/create-instant-clips  
- https://blog.cloudflare.com/media-transformations-for-video-open-beta/  
- https://sumguy.com/owncast-vs-peertube-vs-nginx-rtmp/  

---

## G. Next action

Pick one row from **§E**, add it to `TODO.md` with a number if needed, then implement as a focused PR — don’t try to absorb PingOS/OME wholesale; OnStream’s edge is **API + Expo lab on top of MediaMTX**, not replacing the media server.
