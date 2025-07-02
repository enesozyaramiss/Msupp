import os
import numpy as np
import sounddevice as sd
import keyboard
import threading
import tkinter as tk
from scipy.signal import resample
import whisper
import google.generativeai as genai
import time
from dotenv import load_dotenv

# === WHISPER MODELİ ===
model_whisper = whisper.load_model("small")
samplerate = 48000
#is pc si number 7
device = 7
recording_data = []
recording = False

# .env dosyasını yükle
load_dotenv()

# .env içinden API anahtarını al
api_key = os.getenv("GEMINI_API_KEY")

# === GEMINI AYARLARI ===
genai.configure(api_key=api_key) # <-- API anahtarını koy
generation_config = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 750,
    "response_mime_type": "text/plain",
}
model_gemini = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

# === KONTEXTİ TXT DOSYASINDAN YÜKLE ===
def load_context(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

context_text = load_context("context.txt")

# === GEMINI CHAT OLUŞTUR ===
chat_session = model_gemini.start_chat(
    history=[
        {
            "role": "user",
            "parts": [context_text]
        }
    ]
)

def create_overlay():
    root = tk.Tk()
    root.title("Real-time Q&A Overlay")
    root.attributes('-alpha', 0.95)  # Neredeyse opak
    root.attributes('-topmost', True)
    root.geometry("700x400+100+100")

    text_widget = tk.Text(
        root,
        font=("Consolas", 16, "bold"),  # Daha büyük ve kalın font
        bg="#F0F0F0",                   # Açık gri arka plan, şeffaf hissi verir
        fg="black",
        wrap='word',
        padx=10,
        pady=10
    )
    text_widget.pack(expand=True, fill='both')
    text_widget.insert('end', "System ready. Press F9 to start recording, K to stop.\n\n")
    text_widget.config(state='disabled')

    return root, text_widget

def update_overlay(text_widget, message, header=None):
    text_widget.config(state='normal')
    text_widget.insert('end', "\n" + "=" * 60 + "\n")
    if header:
        text_widget.insert('end', f"{header}\n", "header")
    text_widget.insert('end', message + "\n")
    text_widget.see('end')
    text_widget.config(state='disabled')

# === SES KAYIT ===
def start_recording(text_widget):
    global recording_data, recording
    recording_data = []
    recording = True
    update_overlay(text_widget, "Recording started...", "INFO")
    print("Recording started...")

    def callback(indata, frames, time_info, status):
        if recording:
            recording_data.append(indata.copy())

    stream = sd.InputStream(samplerate=samplerate, channels=2, device=device, callback=callback)
    stream.start()
    return stream

def stop_recording(stream, text_widget):
    global recording
    recording = False
    stream.stop()
    stream.close()

    if not recording_data:
        update_overlay(text_widget, "No audio captured.", "INFO")
        print("No audio captured.")
        return

    combined = np.concatenate(recording_data, axis=0)
    combined = combined[:, 0].astype(np.float32)

    target_samples = int(len(combined) * 16000 / samplerate)
    resampled = resample(combined, target_samples)

    result = model_whisper.transcribe(resampled, language="en")
    text = result["text"].strip()
    update_overlay(text_widget, text, "Transcription")
    print(f"Transcription: {text}")

    if len(text) >= 3:
        try:
            
            message = (
                f"Here is my CV and a set of sample interview Q&A pairs for context. "
                f"CV and Q&A: {context_text} "
                f"My question: {text} "
                f"Step 1: Check if the question exactly matches or closely matches any Q in the Q&A list (use semantic similarity). "
                f"Step 2: If there's a match, return **only** the corresponding A — don't change or summarize it. "
                f"Step 3: If there's no match, generate a natural, professional answer in a friendly and concise tone (max 4-5 sentences). "
                f"Return only the final answer, without mentioning steps or context."
            )
            
            response = chat_session.send_message(message)
            short_response = trim_to_sentences(response.text, 6)
            update_overlay(text_widget, short_response, "Gemini Response")
            print(f"Gemini Response: {short_response}")
        except Exception as e:
            update_overlay(text_widget, f"Gemini error: {e}", "ERROR")
            print(f"Gemini error: {e}")
    else:
        update_overlay(text_widget, "Skipping short or empty transcription.", "INFO")
        print("Skipping short or empty transcription.")

def trim_to_sentences(text, max_sentences):
    sentences = text.split('.')
    trimmed = '.'.join(sentences[:max_sentences]).strip()
    if not trimmed.endswith('.'):
        trimmed += '.'
    return trimmed

# === TUŞ DİNLER ===
def key_listener(text_widget):
    stream = None
    while True:
        if keyboard.is_pressed('esc'):
            update_overlay(text_widget, "Exiting.", "INFO")
            print("Exiting.")
            if stream:
                stream.stop()
                stream.close()
            break

        if keyboard.is_pressed('f9') and not recording:
            stream = start_recording(text_widget)
            while keyboard.is_pressed('f9'):
                time.sleep(0.2)

        if keyboard.is_pressed('k') and recording:
            stop_recording(stream, text_widget)
            while keyboard.is_pressed('k'):
                time.sleep(0.2)

        time.sleep(0.05)

# === BAŞLAT ===
if __name__ == "__main__":
    root, text_widget = create_overlay()
    text_widget.tag_config("header", foreground="yellow", font=("Consolas", 14, "bold"))
    threading.Thread(target=key_listener, args=(text_widget,), daemon=True).start()
    root.mainloop()