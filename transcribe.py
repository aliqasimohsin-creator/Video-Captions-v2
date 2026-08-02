import assemblyai as aai
from group_into_captions import group_words_into_chunks

aai.settings.api_key = "Enter Your Assembly AI API here"

AUDIO_FILE_PATH = "path/to/your/video.mp4"

transcriber = aai.Transcriber()
transcript = transcriber.transcribe(AUDIO_FILE_PATH)

word_data = [
    {
        "text": word.text,
        "start": word.start / 1000,
        "end": word.end / 1000,
    }
    for word in transcript.words
]

caption_chunks = group_words_into_chunks(word_data, chunk_size=2)

for chunk in caption_chunks:
    print(f'"{chunk["text"]}"  start={chunk["start"]:.2f}s  end={chunk["end"]:.2f}s')
