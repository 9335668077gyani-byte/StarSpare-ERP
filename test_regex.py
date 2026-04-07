import sys
from api_sync_engine import TVSApiClient, _force_dict

sys.stdout.reconfigure(encoding='utf-8')

def run():
    client = TVSApiClient("63735")
    client.connect()
    
    # Get Spare Parts Series -> Name map
    spare_map = {}
    cats = client.get_categories() or []
    for c in cats:
        c = _force_dict(c)
        cid = c.get("CATEGORY_ID") or c.get("categoryId")
        if not cid: continue
        mods = client.get_models_by_category(str(cid)) or []
        for m in mods:
            m = _force_dict(m)
            series = str(m.get("series") or m.get("SERIES") or m.get("SERIES_ID") or "")
            name = str(m.get("DESCRIPTION") or m.get("SERIES_NAME") or "")
            if series and name:
                spare_map[series] = name
                
    # Now check Painted Models
    painted = client.get_painted_models("MOTORCYCLE") or []
    hit, miss = 0, 0
    for p in painted:
        p = _force_dict(p)
        mid = p.get("ModelID") or p.get("MODEL_ID") or ""
        s_level = p.get("s_levelName") or ""
        
        # Test if s_level is in spare map
        if s_level in spare_map:
            print(f"Matched Painted {mid} (s_level={s_level}) -> {spare_map[s_level]}")
            hit += 1
        elif mid == "000010000100000017":
            print(f"000017 has s_level={s_level}. NOT in spare map.")
            miss += 1
        else:
            miss += 1
            
    print(f"Hits: {hit}, Misses: {miss}")

if __name__ == "__main__":
    run()
