What is the project — CS2 Panel

# Counter-Strike 2 Community Server Management System

A full-featured web panel and server management system for Counter-Strike 2 community servers, supporting BHOP, Surf, KZ, and 1v1 Aim game modes.

Built with: Django.
Owner: MaxZ AKE Makxsud0831


//
//
//

Main features

🎮 Game server management

5 CS2 dedicated servers (bhop, KZ, 1v1, 2 surf) — Start/Stop, map change, kick/ban/say, RCON commands from the web.
Live online status of servers (A2S query), steam://connect and "Copy IP" buttons.
Homepage with servers grouped by type.

🏆 Leaderboard / record system

SharpTimer timer plugin writes records to PostgreSQL, the site reads them.
Global leaderboard (pagination, cache), top per map, cp/tp (checkpoint/teleport) statistics.
Clickable public profiles /u/<steam_id>/ — anyone can see stats+skins of any player.

🔐 Steam OAuth login — login via Steam, avatar/name automatic.

🎨 Skin Changer (VIP feature)

Server-side WeaponPaints (no VAC ban) — select weapon/knife/glove/agent skin from the web.
Free: default knife for everyone. Skinned: for Pro/VIP.
Loadout is backed up when VIP expires, restored when re-acquired.

💎 VIP system

VIP grant/cancel from admin panel (by day).
FACEIT auto-VIP: automatic 10 days VIP if FACEIT level ≥10.
Reserved slot / VIP priority synced to server.
