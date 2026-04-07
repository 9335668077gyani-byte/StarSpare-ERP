import sys
from api_sync_engine import TVSApiClient

sys.stdout.reconfigure(encoding='utf-8')

def run():
    client = TVSApiClient("63735")
    client.connect()
    
    result = client.get_painted_models_with_colors("MOTORCYCLE")
    colors = result.get("colors", [])
    models = result.get("models", [])
    print(f"Models: {len(models)}, Color entries: {len(colors)}")
    print("First 3 color entries:")
    for c in colors[:3]:
        print(f"  ModelID={c.get('ModelID')}, ColorID={c.get('ColorID')}, name={c.get('name')}, image2={c.get('image2','')[-50:]}")

if __name__ == "__main__":
    run()
