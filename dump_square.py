import sys
import json
from api_sync_engine import TVSApiClient

sys.stdout.reconfigure(encoding='utf-8')

def run():
    client = TVSApiClient("63735")
    if not client.connect():
        print("Failed to connect")
        return
        
    cats = client.get_categories()
    cat_id = None
    for c in cats:
        cname = c.get("CATEGORY_NAME") or c.get("name")
        if cname and cname.upper() == "MOTORCYCLE":
            cat_id = c.get("CATEGORY_ID") or c.get("categoryId")
            break
            
    if not cat_id:
        print("Category not found")
        return
        
    models = client.get_models_by_category(cat_id)
    if not models:
        print("No models returned")
        return
        
    for m in models[:5]:
        print(json.dumps(m, indent=2))

if __name__ == "__main__":
    run()
