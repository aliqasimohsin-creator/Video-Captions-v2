def group_words_into_chunks(words, chunk_size=2):
    chunks = []

    for i in range(0, len(words), chunk_size):
        group = words[i:i + chunk_size]
        chunk_text = " ".join(word["text"] for word in group)
        chunk_start = group[0]["start"]
        chunk_end = group[-1]["end"]

        chunks.append({
            "text": chunk_text,
            "start": chunk_start,
            "end": chunk_end,
            "words": group,
        })

    return chunks


if __name__ == "__main__":
    sample_words = [
        {"text": "hello", "start": 0.0, "end": 0.4},
        {"text": "there", "start": 0.4, "end": 0.9},
        {"text": "friend", "start": 0.9, "end": 1.3},
        {"text": "how", "start": 1.3, "end": 1.5},
    ]

    caption_chunks = group_words_into_chunks(sample_words, chunk_size=2)

    for chunk in caption_chunks:
        print(f'"{chunk["text"]}"  start={chunk["start"]}  end={chunk["end"]}')
