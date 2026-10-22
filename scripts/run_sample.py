"""Run the sample pile once and print the stamps. Local demo check."""

from dotenv import load_dotenv

load_dotenv()

from app.pile import process_pile
from app.samples import SAMPLE_PILE

for event in process_pile(SAMPLE_PILE, seed_memory=True):
    if event.get("status"):
        print("STATUS", event["status"], flush=True)
    elif event.get("error"):
        print("ERROR", event["error"], flush=True)
    elif event.get("done"):
        print("LINE", event["line_one"], flush=True)
        print("LINE", event["line_two"], flush=True)
        for item in event["items"]:
            print("---", item["verdict"], "match", item["matched_id"], flush=True)
            print(item["summary"], flush=True)
            print(item["body"][:120].replace("\n", " "), flush=True)
            if item["script"]:
                print("SCRIPT", item["script"], flush=True)
