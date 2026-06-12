"""Entry point. python main.py "What is hybrid search?" """
import sys
from agent.loop import run

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else input("Question: ")
    result = run(query)
    if result.get("escalated"):
        print(f"[ESCALATED to TA] reason: {result.get('reason')}")
    else:
        print(result.get("answer"))
        print("Sources:", ", ".join(result.get("citations", [])))
