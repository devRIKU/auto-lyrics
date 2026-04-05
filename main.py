import google.genai as genai
from google.genai import types
import time
import os
import requests

def get_lyrics(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if " - " in base_name:
        artist, title = base_name.split(" - ", 1)
        artist = artist.strip()
        title = title.strip()
    else:
        print(f"\\nCould not extract artist and title from filename '{base_name}'.")
        title = input("Enter the name of the song: ").strip()
        artist = input("Enter the name of the artist: ").strip()
    
    print(f"Fetching lyrics for '{title}' by '{artist}' from LRCLIB...")
    try:
        response = requests.get("https://lrclib.net/api/search", params={"track_name": title, "artist_name": artist})
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            lyrics = data[0].get("syncedLyrics") or data[0].get("plainLyrics")
            if lyrics:
                print("Lyrics found!")
                lrc_filename = f"{title} - {artist}.lrc".replace("/", "")
                with open(lrc_filename, "w", encoding="utf-8") as f:
                    f.write(lyrics)
                return lrc_filename
        print("No lyrics found on LRCLIB.")
    except Exception as e:
        print(f"Error fetching lyrics: {e}")
    return None

client = genai.Client()

file_name = "audio.mp3"
lrc_filename = get_lyrics(file_name)

print("uploading audio...")
audio_file = client.files.upload(file=file_name)

while audio_file.state.name == "PROCESSING":
    print(".", end="", flush=True)
    time.sleep(2)
    audio_file = client.files.get(name=audio_file.name)

if audio_file.state.name == "FAILED":
    raise ValueError("audio processing failed. check the file format.")

contents_to_generate = [audio_file]

if lrc_filename and os.path.exists(lrc_filename):
    print("uploading lrc reference...")
    lrc_file = client.files.upload(file=lrc_filename, config={'mime_type': 'text/plain'})
    contents_to_generate.append(lrc_file)

print("generating sync data...")

prompt_text = '''Task: Transcribe the provided audio file with exact word-level timestamps in TTML format.

Instructions:
1. I have provided an audio file and an LRC file containing the lyrics. Use the LRC file as a strict reference for the correct lyrics and approximate line timings.
2. Break down the lines into precise WORD-LEVEL timestamps using 'begin' and 'end' attributes.
3. You MUST format the final output as a valid TTML document following the exact structure below.
4. Each line needs a `<p>` tag, and every word inside the line needs its own `<span>` tag. Keep a trailing space within the `<span>` to separate words.
5. If there is too much instrumental music add a music tag with the timestamp [use motive="music"].

Reference TTML Structure:
<?xml version="1.0" encoding="utf-8"?>
<tt xmlns="http://www.w3.org/ns/ttml">
  <body>
    <div>
      <p begin="00:00:10.000" end="00:00:13.500">
        <span begin="00:00:10.000" end="00:00:10.500">Example </span>
        <span begin="00:00:10.500" end="00:00:11.200">word </span>
      </p>
    </div>
  </body>
</tt>'''
contents_to_generate.append(prompt_text)

response = client.models.generate_content(
    model="gemini-2.5-flash", 
    contents=contents_to_generate
)

with open("output.ttml", "w", encoding="utf-8") as f:
    f.write(response.text)
print("\nDone! Saved to output.ttml")