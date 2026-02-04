#!/usr/bin/env python3
import argparse
from mem0_config import get_config, load_dotenv

load_dotenv()

from mem0 import Memory
from mem0.memory.main import _build_filters_and_metadata


def main():
    parser = argparse.ArgumentParser(description="Search memories from mem0")
    parser.add_argument("--user-id", required=True, help="user id to search")
    parser.add_argument("--query", required=True, help="search query text")
    parser.add_argument("--top-k", type=int, default=5, help="number of results")
    args = parser.parse_args()

    memory = Memory.from_config(get_config())
    _, search_filters = _build_filters_and_metadata(user_id=args.user_id)
    hits = memory._search_vector_store(args.query, search_filters, limit=args.top_k, threshold=0.0)
    for item in hits:
        print(item)


if __name__ == "__main__":
    main()
