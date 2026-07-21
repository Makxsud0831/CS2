# CS2 Panel — Handoff (loyiha topshirig'i)

> Bu hujjat ishni boshqa agentga/yangi session'ga topshirish uchun. Bajarilgan va qolgan ishlar, plugin o'zgarishlari, DB schema, testlar, tuzatilishi kerak bo'lgan narsalar.
> Til: o'zbekcha + texnik inglizcha. Sana: 2026-06-19. **Oxirgi yangilanish: 2026-06-28** (4.5-bo'limga qarang — yangi ishlar).
> ⚠️ Secretlar bu faylda OCHIQ — git remote'ga push qilishdan oldin tozalash/rotate qilish SHART (8-bo'lim).

---

## 1. LOYIHA NIMA

CS2 (Counter-Strike 2) **bhop/surf/kz/aim** community server uchun web panel + server boshqaruv tizimi.
- **Django** sayti: leaderboard, o'yinchi profillari, admin panel, **skin changer** (VIP-only).
- **CS2 dedicated server** (SharpTimer timer plugin bilan) — rekordlar PostgreSQL'ga yoziladi.
- Sayt SharpTimer ma'lumotlarini o'qib, leaderboard/profil ko'rsatadi.
- Egasi: MaxZ (SteamID64: 76561199538815857). Hozir **bitta PC da test** (server+Django+DB+o'yin client birga). Keyin ijara serverga ko'chiriladi.

## 2. TEXNOLOGIYALAR / MUHIT

- **Django 5.2.15** (`F:\cs2panel`), venv: `F:\cs2panel\venv` (Python 3.11). Buyruqlar: `.\venv\Scripts\python.exe manage.py ...`
- **PostgreSQL** `cs_web` (asosiy DB): localhost:5432, postgres/`root123`
- **MySQL 8.0.46** `weaponpaints` (skin changer): localhost:3306, `wp_user`/`wp_pass123` (root: `root123`). Windows service `MySQL80`.
- **DRF** (REST API) + **social_django** (Steam OAuth) + **pymysql** (skin uchun MySQL) + **rcon.source** (RCON) + **python-a2s** (server query).
- CS2 server: `F:\cSERVER`, ishga tushirish: `F:\cSERVER\start.bat` (bhop) va `start_kz.bat` (KZ).
- Public IP: `213.230.86.17` (o'zgaruvchan, dynamic). LAN IP: `192.168.100.92`. ngrok: `utterless-len-endergonic.ngrok-free.dev`.
- OS: Windows 10. Shell: PowerShell (`.\venv\Scripts\...`), psql: `F:\PGadmin\bin\psql.exe`, mysql: `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe`.

## 3. SERVERLAR (DB: servers_gameserver jadvali)

| id | nom | tur | port | install | bat | map / workshop |
|----|-----|-----|------|---------|-----|----------------|
| 1 | Sheyx | bhop | 27015 | F:\cSERVER | start.bat | bhop_emevaelx3 (3070509095) |
| 2 | MaxZ KZ | kz | 27016 | F:\cSERVER | start_kz.bat | kz_phamous (3104579274) |
| 3 | 1vs1 | 1v1 | 27017 | **E:\cSERVER_1v1** (ALOHIDA install) | start_1v1.bat | Duels Aim (3405086109) |
| 4 | Surf #1 | surf | 27018 | F:\cSERVER | start_surf.bat | surf_nyx (3129698096) |
| 5 | Surf #2 | surf | 27019 | F:\cSERVER | start_surf2.bat | surf_boreas (3133346713) |

- **`server_type` maydoni** (surf/bhop/kz/1v1) — homepage guruhlash uchun. RCON parol (hammasi): `parol123`.
- **GSLT (har biri o'ziniki):** bhop `D9FA3142F6D2550A43772EE444F4C0DB`, KZ `182EFBDD03DBA1DB21102F207F6C4183`, 1v1 `536222AA143DD4EFF087B5599B9A86B1`, surf1 `3D51507D071703B4116AC4A812DF0CCF`, surf2 `8790C43CCBE85B3A64D74FAEAEAE44AE`. Steam Web API key: `754F25FAD50FA8DD24A840A1559FD354`.
- **⚠️ ALOHIDA INSTALL:** 1v1 server `E:\cSERVER_1v1` (SSD) — chunki K4-Arenas (faol arena plugin) bhop/kz/surf'ni buzadi. Har mod alohida install kerak bo'lganda plagini boshqacha. Bog'liq: prod-deploy-plan memory.

## 4. BAJARILGAN ISHLAR (DONE)

### Backend (Django apps: users, servers, records)
- **users**: custom User (AbstractUser), SteamProfile (steam_id64, display_name, avatar_url), Subscription (basic/pro/vip + expires_at), Steam OAuth login.
- **servers**: GameServer, ServerConfig, ServerMap (tier/stages/bonus qo'shilgan), MapConfig. RCON (kick/ban/say/restart/map/exec), A2S status, start/stop (bat orqali), Map Pool & Tier API.
- **records**: PlayerRecord, RecordHistory, MapCompletion (Django ichki), STPlayerRecord/STPlayerStats (managed=False, SharpTimer jadvallari), CheckpointStat (cp/tp). Submit run, leaderboard, player search, API token auth.
- **API token**: CS2 server uchun `cs2server_bot` user + token `968e25e03a9d3155f5a63d9a0d00526f772b0258`.

### Frontend (Django templates, `F:\cs2panel\templates\`)
- `base.html` (nav + Steam login/logout), `home.html` (server kartalar + Copy IP, Cybershoke uslubida map rasm fon),
- `leaderboard.html` (global top, paginatsiya 50/sahifa, cache 60s), `map_leaderboards.html` + `map_detail.html` (har map top + cp/tp ustunlari),
- `records.html` (so'nggi rekordlar), `profile.html` (Steam stats + avatar),
- `panel.html` (admin: server start/stop/map/kick/ban/rcon/players + VIP boshqaruv),
- `skins.html` (skin changer — slot grid, modal, save tugmasi),
- `error.html` (do'stona xato sahifa — Steam 503 va h.k.).

### Steam login
- `SOCIAL_AUTH_STEAM_API_KEY` = STEAM_API_KEY. Pipeline `users/pipeline.py save_steam_profile` — `details['player']` dan steamid/nom/avatar oladi (response dict EMAS, OpenID obyekti — buni tushunish muhim). Avatar: `avatarfull`. Username auto-generatsiya ("AVGMaxZe2a..."), saytda `user.steam_display_name` (chiroyli nom) ko'rsatiladi.
- Xato handling: `SocialAuthExceptionMiddleware` + `SOCIAL_AUTH_RAISE_EXCEPTIONS=False` → `/auth-error/` do'stona sahifa.

### Admin panel (`/panel/`, faqat is_staff)
- Server: Start/Stop (bat), Map (workshop ID yoki nom), Say, Kick/Ban, RCON, O'yinchilar ro'yxati. JS fetch + CSRF.
- VIP boshqaruv: steamid/username bo'yicha VIP berish (kun bilan) / bekor qilish, VIP ro'yxat.
- MaxZ akkaunti is_staff=is_superuser=True.

### Skin changer (VIP-only) — TO'LIQ
- **Server-side WeaponPaints** (VAC ban yo'q). Web tanlagich `/skins/`: Qurol, Pichoq, Qo'lqop, **Agent CT/T** slotlari + default rasmlar.
- Staging + **Saqlash tugmasi** (tasodifan bosilsa skin o'zgarmaydi). Batch save `/skins/save-all/`.
- VIP gate: `user.is_staff or user.is_premium()`. O'yin-ichi komandalar (`!ws`/`!knife`/`!gloves`) o'chirilgan, faqat `!wp` (refresh) qolgan → skin faqat web orqali.
- `cs2panel/skins_service.py` — pymysql orqali to'g'ridan-to'g'ri MySQL (parametrlangan). Skin data: `F:\cSERVER\...\WeaponPaints\data\skins_en.json`, `gloves_en.json`, `agents_en.json`.

## 4.5 YANGI ISHLAR (2026-06-28 sessiya) — BAJARILGAN

### Xavfsizlik (security-hardening-plan memory) — 1–3 bosqich TUGADI
- **1-bosqich:** secretlar `.env` ga (`python-dotenv`), `env_required()` fail-loud, `.gitignore` (.env + .idea/dataSources). settings.py env-driven (DEBUG/ALLOWED_HOSTS/HTTPS/HSTS/secure cookie prod'da auto). YANGI SECRET_KEY. `requirements.txt`. `check --deploy` toza. XSS toza (|safe yo'q).
- **2-bosqich:** RCON buyruq whitelist/blocklist (`servers/services.py: rcon_command_allowed`, zanjir-injection himoyasi) generic endpointlarda. `records/permissions.py: IsTrustedServer` — `submit_checkpoints` faqat `TRUSTED_SERVER_IPS` dan.
- **3-bosqich:** Argon2 (`argon2-cffi`), `django-ratelimit` (token endpoint 5/daq, `RateLimitedObtainAuthToken`), admin URL maxfiy (`ADMIN_URL`=maxz-cp-7h3k9q/), `pip-audit` (cryptography 49.0.0 fix). 134 test o'tadi.
- **2FA KEYINGA** (prod deploy bilan). Firewall/Cloudflare/Redis/Sentry/backup = 4-bosqich.

### Sayt (Django) yangi xususiyatlar
- **Public profil** `/u/<steam_id>/` — har kirgan user istalgan o'yinchi profilini ko'radi (stats+VIP+skinlar). `_profile_context` helper. Leaderboard + map_detail qatorlari **bosiladigan** (steam_id).
- **Homepage:** serverlar **TUR bo'yicha guruhlangan** (surf/bhop/kz/1v1 label), jonli online holat (`/api/servers/public-status/` AllowAny 20s cache), **steam://connect** tugmasi. IP HTML'da statik `192.168.100.92` (test), `map_image` `/static/maps/` dan (surf_nyx.jpg, surf_boreas.jpg). STATICFILES_DIRS qo'shildi.
- **Admin panel qayta dizayn:** server kartalari (Copy IP + ⚙ Sozlash toggle), VIP qidiruv (`/panel/users/search/`), natija kartalari → profil, eng yangi 30 obunachi.
- **Bepul default pichoq:** `/skins/` har authenticated user'ga; bepul = default pichoq (`/skins/save-basic/`, paint=0 majburiy backend), skinli = Pro/VIP (`_can_paint_skins`). Seed/pattern (pichoq+qo'lqop). Skin rasm 404 fix (ByMykel CDN).

### VIP tizimi (skin-changer-setup + community-plugins memory)
- **FACEIT auto-VIP:** login'da level ≥10 → 10 kun VIP, BIR MARTALIK (`SteamProfile.faceit_vip_granted`). `FACEIT_API_KEY` env kerak. `users/faceit.py`.
- **VIP tugaganда skin loadout saqlash:** `expire_vips` komandasi → backup (`SkinBackup` Postgres) + WeaponPaints'dan o'chiradi; VIP qayta olinса tiklanadi. (Steam inventory'ga ko'chirish IMKONSIZ — fake skin.)
- **Reserved slot / VIP priority:** `cs2panel/admin_sync.py` aktiv VIP'larni `admins.json` ga (@css/reservation) yozadi + RCON `css_admins_reload`. CS2-ReservedSlots plagini connect'da o'qiydi.

### Yangi serverlar + pluginlar (community-plugins, k4-arenas-fork memory)
- **1v1 server** (E install): K4-Arenas (FORK qilingan — `!duel` WASD menyu, round-settings faqat ak47/m4a1s/awp/deagle, give-knife=false + mp_*_default_melee "" pichoq-tushish fix). RockTheVote (RTV). FunSize (random hajm — vizual ishlaydi, hitbox CS2 cheklovi). WeaponPaints ham qo'shilgan.
- **CS2-SimpleAdmin** (F install, bhop/kz/surf): `cs2admin` MySQL DB, owner root admin. Ban/mute/gag/kick.
- **SharpTimer ochko:** `sharptimer_global_rank_points_enabled true`, har MapData JSON'ga `"MapTier":"1"` (STRING bo'lishi SHART — son crash qiladi). bhop_emevaelx3 end-zona kattalashtirildi (teleport zonani qoplash). bhop tezlik: airaccelerate 2000, wishspeed 40.

## 5. CS2 SERVER PLUGINLARI VA CONFIG O'ZGARISHLARI

### Custom plaginlar (manba: `F:\cSERVER\plugins_src\`, build: `dotnet build -c Release`, dll → `addons/counterstrikesharp/plugins/<Name>/`)
1. **MapRestartTimer** (`F:\cSERVER\plugins_src\MapRestartTimer\`):
   - 500 daq map reload (config.json `RestartMinutes`) — HOZIR `0` = O'CHIRILGAN (bir PC da reload ~1 daq muzlatadi). Alohida serverda 500 qilinadi.
   - Warmup/team-intro muzlashini tuzatadi (har map start).
   - Map turiga qarab `sharptimer_checkpoints_enabled` (kz_ → true, boshqa → false).
2. **KzCpStats** (`F:\cSERVER\plugins_src\KzCpStats\`):
   - `!cp`/`!tp` ni sanaydi, finish'ni map JSON end-zone orqali aniqlaydi, chatда ko'rsatadi, Django `/api/records/checkpoints/` ga API token bilan yuboradi.
   - config.json: ApiUrl, ApiToken (968e25...).

### Tayyor plaginlar (yuklab o'rnatilgan)
- **WeaponPaints** (Nereziel build 423) + dependency zanjiri: **AnyBaseLib** (shared), **PlayerSettings**, **MenuManagerCore** (NickFox007). Bularsiz WeaponPaints yuklanmaydi ("menu:nfcore" xatosi). Dependency'lar faqat to'liq server restart'da yuklanadi.
- SharpTimer 0.4.0 (poor-sharptimer), CS2Fixes.

### Muhim config o'zgarishlari (qaytarib qo'yilmasin!)
- `addons/counterstrikesharp/configs/core.json`: **`FollowCS2ServerGuidelines: false`** — KRITIK, aks holda qo'lqop/StatTrak ishlamaydi ("m_iEntityQuality" xatosi). To'liq restart kerak.
- `cfg/SharpTimer/config.cfg`: `sharptimer_checkpoints_enabled true` (asosiy manba; map-cfg dan o'qilmaydi).
- `cfg/SharpTimer/MapData/MapExecs/bhop_.cfg`: round/movement bhop sozlamalari; `mp_timelimit 0` (reload plagin orqali); `mp_do_warmup_period 0`; `mp_team_intro_time 0`; `mp_ignore_round_win_conditions true`.
- `cfg/SharpTimer/MapData/MapExecs/aim_.cfg`, `dm_.cfg` — yaratilgan (otishma rejimi, bhop reset, damage ON).
- `cfg/SharpTimer/MapData/kz_phamous.json` — KZ map zonalari (MapStartC1/C2, MapEndC1/C2, RespawnPos). Z balandligi sozlangan.
- `gameinfo.gi` ConVars: mp_team_intro_time/mp_do_warmup_period/mp_warmuptime defaultlari 0 (faqat full restart'da o'qiladi).
- `WeaponPaints.json`: DB krediti (weaponpaints/wp_user/wp_pass123), Website=ngrok/skins, Command* bo'sh (faqat wp refresh).
- `MenuManagerCore.json`: `DefaultMenu: ChatMenu` (ButtonMenu markaziy HUD SharpTimer timer bilan to'qnashadi — lekin endi o'yin-ichi menyu ishlatilmaydi).
- `start.bat`/`start_kz.bat`: `+map de_dust2` keyin `+host_workshop_map <id>` (to'g'ridan-to'g'ri workshop boot ishlamaydi).

## 6. DATABASE SCHEMA MUHIM NUQTALARI

### PostgreSQL (cs_web)
- SharpTimer jadvallari (managed=False): `PlayerRecords`, `PlayerStats`, `PlayerStageTimes`.
- **GOTCHA:** SharpTimer migration mexanizmi buzilgan ("CommandText not initialized") — schema QO'LDA tuzatilgan. KRITIK PK'lar: `PlayerRecords` PK = `(MapName,SteamID,Style,Mode)`, `PlayerStageTimes` PK = `(MapName,SteamID,Stage,Style,Mode)`. Aks holda SharpTimer vaqt saqlay olmaydi (`42P10 ON CONFLICT` xatosi). Qo'shilgan ustunlar: PlayerStats'da HidePlayers/Mode/HideChatSpeed/HideWeapon, PlayerRecords'da Mode(TEXT), PlayerStageTimes'da Style/Mode. Ustun nomlari: `PlayerName` (SteamName EMAS).
- Django jadvallari: standart (users_*, servers_*, records_*).

### MySQL (weaponpaints) — WeaponPaints o'zi yaratgan
- `wp_player_skins` (PK steamid,weapon_team,weapon_defindex; weapon_paint_id, weapon_wear, weapon_seed...), `wp_player_knife` (knife=weapon_name), `wp_player_gloves` (weapon_defindex), `wp_player_agents` (agent_ct, agent_t), `wp_player_music`, `wp_player_pins`.
- Pichoq = MODEL (wp_player_knife) + SKIN (wp_player_skins defindex+paint); qo'lqop = wp_player_gloves + wp_player_skins; agent = wp_player_agents (model yo'li). Hammasi IKKALA jamoa (team 2,3) uchun yoziladi.
- steamid = SteamID64 (Django SteamProfile bilan bir xil).

## 7. TESTLAR

- `servers/tests.py` — 48 test (status, RCON kick/ban/say/restart, start/stop, map pool, set current map, players-via-RCON-users, ServerLauncher). Hammasi o'tadi.
- `records/tests.py` — RecordService, submit run, leaderboard, my records, player search, token auth, CheckpointSubmit. Hammasi o'tadi.
- `users/tests.py` — User, Subscription, SteamProfile.
- Ishga tushirish: `.\venv\Scripts\python.exe manage.py test`. Jami ~100+ test.
- ESLATMA: cache testlar orasida ifloslanmasligi uchun servers BaseTestCase.setUp da `cache.clear()`. Skin changer (skins_service, pymysql) uchun avtomatik test YO'Q — qo'lda tekshirilgan. Plugin (C#) testlari yo'q.

## 8. QILINISHI KERAK (TODO) — tartib bilan

### A) Xavfsizlik — 1–3 bosqich TUGADI ✅ (4.5-bo'lim). QOLGAN:
- [ ] **🔴 SECRET ROTATION (push'dan oldin SHART):** kalitlar git tarixida + bu HANDOFF.md ichida OCHIQ (RCON parol123, GSLT'lar, DB parollar, bot token, Steam API key). GitHub'ga push qilishdan oldin: Steam API key qayta generatsiya, DB parollar (root123/wp_pass123), RCON, GSLT'lar, bot token ALMASHTIRISH + bu fayldan secretlarni olib tashlash/gitignore.
- [ ] **4-bosqich (prod deploy bilan):** firewall (RCON/DB portlari), HTTPS (Caddy/Nginx+LE), Cloudflare/WAF + origin firewall, Redis (cache/ratelimit), DB backup (pg_dump+mysqldump avtomatik+offsite), Sentry, **2FA** (django-otp, admin). `TRUSTED_SERVER_IPS` yoqish.

### B) VIP sotish (to'lov) — daromad [QILINMAGAN]
- [ ] Payme/Click (O'zbekiston) yoki Stripe webhook — signature tekshirib VIP berish (`vip_grant` mantig'iga ulanadi, skin-restore + reserved-slot sync avtomatik bo'ladi). Frontendga ishonmaslik.

### C) Prod deploy (prod-deploy-plan memory) [QILINMAGAN]
- [ ] **VDS olish** (L3/L4 anti-DDoS UDP uchun SHART — Cloudflare bepul faqat web/HTTP). ≥8GB RAM, statik IP, CIS'ga yaqin. Qaror: har MOD uchun alohida install (bir install → ko'p instance, port+GSLT bilan). Gunicorn/Nginx, "slow server frame" bitta PC quvvati cheklovi.
- [ ] Deploy'da: `SERVER_PUBLIC_IP`/homepage IP'ni public IP'ga, `ADMIN_CONFIG_PATHS` yangi yo'llarga, FACEIT key, `expire_vips` cron/Task Scheduler.

### D) Sozlash kerak (hozirgi sessiyadan) [foydalanuvchi qiladi]
- [ ] **Serverlarni restart** — yangi pluginlar yuklanishi uchun (F: SimpleAdmin+ReservedSlots; E: K4-Arenas+RTV+FunSize+ReservedSlots+WeaponPaints).
- [ ] **FACEIT_API_KEY** ni `.env` ga (developers.faceit.com).
- [ ] **`expire_vips`** ni Task Scheduler'ga (har soat) — skin arxiv + reserved-slot.
- [ ] CS2-ReservedSlots config: `reservedSlots` soni + kick type.
- [ ] Surf #1/#2 + boshqa maplarga `MapData/<map>.json` zona + `MapTier`(STRING) + ochko tekshirish.

### E) Polish / kuzatiladigan
- [ ] FunSize hitbox: CS2 dvigatel masshtablamaydi — yumshoq masshtab (0.7–1.4x) yoki vizual hazil.
- [ ] Music kit / pin tanlagich (WeaponPaints qo'llaydi). KZ stage rekordlari UI. Qo'lqop default rasm. Doppler seed.
- [ ] Skin web UI: pichoq model ba'zan eski qiymatda (qayta tekshirish).

## 9. ESLAB QOLINGAN (memory fayllar)
`C:\Users\mmaqs\.claude\projects\F--cs2panel\memory\` (MEMORY.md = indeks):
- `cs2-server-setup.md` — serverlar, plaginlar, SharpTimer DB gotcha + ochko/MapTier, homepage dinamik
- `security-hardening-plan.md` — xavfsizlik 1–3 bosqich (TUGADI) + qolgan
- `skin-changer-setup.md` — WeaponPaints + VIP tier + FACEIT auto-VIP + loadout arxivlash
- `prod-deploy-plan.md` — VDS olish→deploy tartibi, DDoS mantiqi, har-mod-alohida-install
- `k4-arenas-fork.md` — 1v1 K4-Arenas fork (!duel menyu), net8/1.0.335 build gotcha
- `community-plugins.md` — RTV, CS2-SimpleAdmin (cs2admin DB), ReservedSlots+admin_sync, FunSize

## 10. ASOSIY URL'LAR
`/` home (guruhlangan + connect), `/leaderboard/` (bosiladigan), `/leaderboard/maps/`, `/records/`, `/profile/`, **`/u/<steam_id>/`** (public profil), `/panel/` (admin), `/skins/` (bepul=default pichoq, Pro/VIP=skinli), `/auth/login/steam/`, `/auth-error/`.
- API: `/api/servers/...` (+ `/api/servers/public-status/` AllowAny), `/api/records/...`, `/api/auth/token/` (ratelimit), `/panel/users/search/`, `/skins/save-basic/`.
- Admin URL: maxfiy `/maxz-cp-7h3k9q/` (eski `/admin/` 404). Management: `manage.py expire_vips`.
