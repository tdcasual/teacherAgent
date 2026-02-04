#!/usr/bin/env python3
import argparse
from mem0_config import get_config, load_dotenv

load_dotenv()

from mem0 import Memory
from mem0.memory.main import _build_filters_and_metadata


def main():
    parser = argparse.ArgumentParser(description="Write a memory to mem0")
    parser.add_argument("--user-id", required=True, help="user id, e.g., teacher:physics or student:NAME")
    parser.add_argument("--text", required=True, help="memory text (confirmed summary)")
    parser.add_argument("--infer", action="store_true", help="use LLM to extract memory")
    args = parser.parse_args()

    memory = Memory.from_config(get_config())
    messages = [{"role": "user", "content": args.text}]
    processed_metadata, effective_filters = _build_filters_and_metadata(user_id=args.user_id)
    result = memory._add_to_vector_store(messages, processed_metadata, effective_filters, infer=args.infer)
    print({"results": result})


if __name__ == "__main__":
    main()
