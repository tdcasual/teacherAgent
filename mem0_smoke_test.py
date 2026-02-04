from mem0_config import get_config, load_dotenv

load_dotenv()

from mem0 import Memory
from mem0.memory.main import _build_filters_and_metadata


def main():
    memory = Memory.from_config(get_config())

    messages = [
        {
            "role": "user",
            "content": (
                "【教师讨论】EX2403_PHY：Q15全班0分，Q9/Q3/Q7/Q14为高失分题。"
                "已确认客观题答案与Q12(3)数值。"
            ),
        }
    ]

    # Avoid thread-related issues in local Qdrant mode by calling internal helpers directly
    processed_metadata, effective_filters = _build_filters_and_metadata(user_id="teacher:physics")
    add_result = memory._add_to_vector_store(messages, processed_metadata, effective_filters, infer=True)
    print("add_result:", {"results": add_result})

    _, search_filters = _build_filters_and_metadata(user_id="teacher:physics")
    hits = memory._search_vector_store("Q15 失分", search_filters, limit=5, threshold=0.0)
    print("search_hits:", hits[:3])


if __name__ == "__main__":
    main()
