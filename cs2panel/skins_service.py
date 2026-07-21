"""
WeaponPaints skin changer servisi.
MySQL (weaponpaints DB) ga to'g'ridan-to'g'ri pymysql orqali yozadi/o'qiydi.
Barcha so'rovlar parametrlangan (SQL injection xavfsiz).
"""
import json
import functools
import os

import pymysql
import pymysql.cursors
from django.conf import settings

# CS2 jamoalari: 2 = T, 3 = CT. Skinni ikkala jamoaga ham yozamiz.
TEAMS = (2, 3)


def _is_knife(weapon_name):
    return 'knife' in weapon_name or weapon_name == 'weapon_bayonet'


def _conn():
    db = settings.WEAPONPAINTS_DB
    return pymysql.connect(
        host=db['host'], port=db['port'], user=db['user'],
        password=db['password'], database=db['database'],
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5, autocommit=True,
    )


@functools.lru_cache(maxsize=1)
def _load_raw():
    with open(settings.WEAPONPAINTS_SKINS_JSON, encoding='utf-8') as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def _load_gloves_raw():
    path = os.path.join(os.path.dirname(settings.WEAPONPAINTS_SKINS_JSON), 'gloves_en.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _models(raw, name_filter):
    """raw dan model ro'yxati: [{defindex, weapon_name, display_name, default_image}]."""
    models = {}
    for s in raw:
        di = s['weapon_defindex']
        wn = s.get('weapon_name', '')
        if not name_filter(wn):
            continue
        if di not in models:
            display = s.get('paint_name', wn).split('|')[0].strip()
            models[di] = {
                'defindex': di, 'weapon_name': wn, 'display_name': display or wn,
                'default_image': '',
            }
        # default (paint 0) rasmini eslab qolamiz
        if str(s.get('paint')) == '0' and s.get('image'):
            models[di]['default_image'] = s['image']
        elif not models[di]['default_image'] and s.get('image'):
            models[di]['default_image'] = s['image']  # zaxira: birinchi rasm
    return sorted(models.values(), key=lambda w: w['display_name'])


def default_knife_image():
    for s in _load_raw():
        if s.get('weapon_name') == 'weapon_knife' or s.get('weapon_name') == 'weapon_bayonet':
            if s.get('image'):
                return s['image']
    return ''


def load_weapons():
    """Oddiy qurollar (pichoqsiz)."""
    return _models(_load_raw(), lambda wn: not _is_knife(wn))


def load_knives():
    """Pichoq modellari."""
    return _models(_load_raw(), _is_knife)


def knife_model(weapon_name):
    """weapon_name bo'yicha HAQIQIY pichoq modelini qaytaradi yoki None.
    Backend validatsiyasi uchun — foydalanuvchi ixtiyoriy weapon_name yubora olmasin."""
    wn = (weapon_name or '').strip()
    for k in load_knives():
        if k['weapon_name'] == wn:
            return k
    return None


def load_gloves():
    """Qo'lqop modellari (gloves_en.json, weapon_name yo'q)."""
    models = {}
    for s in _load_gloves_raw():
        di = s['weapon_defindex']
        if di == 0:
            continue  # default
        if di not in models:
            display = s.get('paint_name', '').split('|')[0].strip().lstrip('★').strip()
            models[di] = {'defindex': di, 'display_name': display or f'Gloves {di}'}
    return sorted(models.values(), key=lambda w: w['display_name'])


def gloves_skins(defindex):
    """Bitta qo'lqop modeli uchun paintlar."""
    out = []
    for s in _load_gloves_raw():
        if s['weapon_defindex'] == defindex:
            out.append({'paint': str(s['paint']), 'name': s.get('paint_name', ''), 'image': s.get('image', '')})
    return out


@functools.lru_cache(maxsize=1)
def _load_agents_raw():
    path = os.path.join(os.path.dirname(settings.WEAPONPAINTS_SKINS_JSON), 'agents_en.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_agents(team):
    """Berilgan jamoa uchun agentlar (team 2=T, 3=CT): [{model, name, image}]."""
    out = []
    for a in _load_agents_raw():
        m = a.get('model')
        if a.get('team') == team and m and m != 'null':
            out.append({'model': m, 'name': a.get('agent_name', ''), 'image': a.get('image', '')})
    return out


@functools.lru_cache(maxsize=1)
def _agent_index():
    return {a['model']: {'name': a.get('agent_name', ''), 'image': a.get('image', '')}
            for a in _load_agents_raw() if a.get('model') and a['model'] != 'null'}


def agent_info(model):
    return _agent_index().get(model) if model else None


def get_player_agents(steamid):
    """{'agent_ct': model|None, 'agent_t': model|None}."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT agent_ct, agent_t FROM wp_player_agents WHERE steamid=%s", [str(steamid)])
        return cur.fetchone() or {'agent_ct': None, 'agent_t': None}


def set_agent(steamid, team, model):
    """team 3=CT (agent_ct), 2=T (agent_t). model yo'li saqlanadi."""
    col = 'agent_ct' if int(team) == 3 else 'agent_t'
    sql = (f"INSERT INTO wp_player_agents (steamid, {col}) VALUES (%s, %s) "
           f"ON DUPLICATE KEY UPDATE {col}=VALUES({col})")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, [str(steamid), model])


@functools.lru_cache(maxsize=1)
def _skin_index():
    """(defindex, paint) -> {name, image} — slotda joriy skinni ko'rsatish uchun."""
    idx = {}
    for s in _load_raw():
        idx[(s['weapon_defindex'], str(s['paint']))] = {
            'name': s.get('paint_name', ''), 'image': s.get('image', '')}
    for s in _load_gloves_raw():
        idx[(s['weapon_defindex'], str(s['paint']))] = {
            'name': s.get('paint_name', ''), 'image': s.get('image', '')}
    return idx


def skin_info(defindex, paint):
    """Bitta skin haqida {name, image} yoki None."""
    return _skin_index().get((int(defindex), str(paint)))


def skins_for_weapon(defindex):
    """Bitta qurol uchun barcha skinlar: [{paint, name, image}]."""
    out = []
    for s in _load_raw():
        if s['weapon_defindex'] == defindex:
            out.append({
                'paint': str(s['paint']),
                'name': s.get('paint_name', ''),
                'image': s.get('image', ''),
            })
    return out


def get_player_skins(steamid):
    """O'yinchining tanlagan skinlari: {weapon_defindex: weapon_paint_id}."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT weapon_defindex, weapon_paint_id FROM wp_player_skins "
            "WHERE steamid=%s AND weapon_team=%s",
            [str(steamid), TEAMS[1]],
        )
        return {row['weapon_defindex']: row['weapon_paint_id'] for row in cur.fetchall()}


def get_player_seeds(steamid):
    """O'yinchining skinlari uchun seed (pattern): {weapon_defindex: weapon_seed}."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT weapon_defindex, weapon_seed FROM wp_player_skins "
            "WHERE steamid=%s AND weapon_team=%s",
            [str(steamid), TEAMS[1]],
        )
        return {row['weapon_defindex']: row['weapon_seed'] for row in cur.fetchall()}


_SKIN_SQL = (
    "INSERT INTO wp_player_skins "
    "(steamid, weapon_team, weapon_defindex, weapon_paint_id, weapon_wear, weapon_seed) "
    "VALUES (%s, %s, %s, %s, 0.000001, %s) "
    "ON DUPLICATE KEY UPDATE weapon_paint_id=VALUES(weapon_paint_id), weapon_seed=VALUES(weapon_seed)"
)


def _clamp_seed(seed):
    """Seed (pattern) 0..1000 oralig'iga keltiriladi."""
    try:
        return max(0, min(1000, int(seed)))
    except (TypeError, ValueError):
        return 0


def set_skin(steamid, defindex, paint_id, seed=0):
    """Skinni ikkala jamoa uchun saqlaydi (upsert). seed = pattern (0..1000)."""
    seed = _clamp_seed(seed)
    with _conn() as conn, conn.cursor() as cur:
        for team in TEAMS:
            cur.execute(_SKIN_SQL, [str(steamid), team, int(defindex), int(paint_id), seed])


def get_player_knife(steamid):
    """O'yinchining tanlagan pichoq modeli (weapon_name) yoki None."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT knife FROM wp_player_knife WHERE steamid=%s LIMIT 1", [str(steamid)])
        row = cur.fetchone()
        return row['knife'] if row else None


def set_knife(steamid, weapon_name, defindex, paint_id, seed=0):
    """Pichoq MODELI (wp_player_knife) + SKIN (wp_player_skins) ni ikkala jamoaga yozadi."""
    seed = _clamp_seed(seed)
    knife_sql = (
        "INSERT INTO wp_player_knife (steamid, weapon_team, knife) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE knife=VALUES(knife)"
    )
    with _conn() as conn, conn.cursor() as cur:
        for team in TEAMS:
            cur.execute(knife_sql, [str(steamid), team, weapon_name])
            cur.execute(_SKIN_SQL, [str(steamid), team, int(defindex), int(paint_id), seed])


def get_player_gloves(steamid):
    """O'yinchining tanlagan qo'lqop defindex'i yoki None."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT weapon_defindex FROM wp_player_gloves WHERE steamid=%s LIMIT 1", [str(steamid)])
        row = cur.fetchone()
        return row['weapon_defindex'] if row else None


def set_gloves(steamid, defindex, paint_id, seed=0):
    """Qo'lqop MODELI (wp_player_gloves) + SKIN (wp_player_skins) ni ikkala jamoaga yozadi."""
    seed = _clamp_seed(seed)
    gloves_sql = (
        "INSERT INTO wp_player_gloves (steamid, weapon_team, weapon_defindex) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE weapon_defindex=VALUES(weapon_defindex)"
    )
    with _conn() as conn, conn.cursor() as cur:
        for team in TEAMS:
            cur.execute(gloves_sql, [str(steamid), team, int(defindex)])
            cur.execute(_SKIN_SQL, [str(steamid), team, int(defindex), int(paint_id), seed])


# --- VIP tugaganda loadout arxivlash / tiklash ---
# Jadval nomlari qat'iy ro'yxat (foydalanuvchi kiritmaydi) — SQL injection xavfsiz.
_WP_TABLES = ('wp_player_skins', 'wp_player_knife', 'wp_player_gloves',
              'wp_player_agents', 'wp_player_music', 'wp_player_pins')


def export_loadout(steamid):
    """O'yinchining barcha WeaponPaints satrlarini {jadval: [satrlar]} qilib qaytaradi."""
    out = {}
    with _conn() as conn, conn.cursor() as cur:
        for t in _WP_TABLES:
            try:
                cur.execute(f"SELECT * FROM {t} WHERE steamid=%s", [str(steamid)])
                out[t] = cur.fetchall()
            except Exception:
                out[t] = []
    return out


def clear_loadout(steamid):
    """O'yinchining barcha WeaponPaints satrlarini o'chiradi (skin ko'rinmay qoladi)."""
    with _conn() as conn, conn.cursor() as cur:
        for t in _WP_TABLES:
            try:
                cur.execute(f"DELETE FROM {t} WHERE steamid=%s", [str(steamid)])
            except Exception:
                pass


def import_loadout(steamid, data):
    """export_loadout dan kelgan ma'lumotni qayta yozadi (VIP tiklanganда)."""
    if not data:
        return
    with _conn() as conn, conn.cursor() as cur:
        for t, rows in data.items():
            if t not in _WP_TABLES or not rows:
                continue
            for row in rows:
                if not row:
                    continue
                row = dict(row)
                row['steamid'] = str(steamid)
                cols = list(row.keys())
                collist = ', '.join(f"`{c}`" for c in cols)
                placeholders = ', '.join(['%s'] * len(cols))
                updates = ', '.join(f"`{c}`=VALUES(`{c}`)" for c in cols)
                try:
                    cur.execute(
                        f"INSERT INTO {t} ({collist}) VALUES ({placeholders}) "
                        f"ON DUPLICATE KEY UPDATE {updates}",
                        [row[c] for c in cols],
                    )
                except Exception:
                    pass
