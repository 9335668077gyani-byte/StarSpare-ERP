import sys
import json
from api_sync_engine import TVSApiClient

sys.stdout.reconfigure(encoding='utf-8')

def run():
    client = TVSApiClient("63735")
    if not client.connect():
        print("Failed to connect")
        return
        
    models = client.get_painted_models("MOTORCYCLE")
    if not models:
        print("No models returned")
        return
        
    # Print the first 5 models to inspect the keys and values
    for m in models[:5]:
        print(json.dumps(m, indent=2))

if __name__ == "__main__":
    run()
