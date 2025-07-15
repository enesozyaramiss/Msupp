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
import ctypes
import ctypes.wintypes

# === WHISPER MODELİ ===
model_whisper = whisper.load_model("small")
samplerate = 48000
#is pc si number 7
device = 7
recording_data = []
recording = False

# === GEMINI AYARLARI ===
genai.configure(api_key="GEMINI_API_KEY")  # <-- API anahtarını koy
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

def exclude_window_from_capture(hwnd):
    # Windows 10 2004+ için ekran paylaşımından pencereyi hariç tut
    WDA_EXCLUDEFROMCAPTURE = 0x11
    SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
    SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
    SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL
    result = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    if not result:
        print("⚠️ Failed to exclude window from capture.")
    else:
        print("✅ Overlay excluded from screen capture.")

def setup_window_exclusion(root):
    """Setup window exclusion after the window is properly created"""
    def exclude_after_render():
        # Wait for window to be fully rendered
        root.update_idletasks()
        time.sleep(0.1)  # Small delay to ensure window is ready
        
        # Try to get HWND
        hwnd = ctypes.windll.user32.FindWindowW(None, "Real-time Q&A Overlay")
        if hwnd:
            exclude_window_from_capture(hwnd)
        else:
            print("⚠️ HWND not found.")
    
    # Schedule the exclusion setup after window creation
    root.after(100, exclude_after_render)

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
    
    # Setup window exclusion after window is created
    setup_window_exclusion(root)

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
                f"You are acting as a senior data scientist being interviewed for a technical position.\n"
                f"Here is the candidate's CV and previous Q&A examples:\n\n"
                f"{context_text}\n\n"
                f"The interviewer asked the following question:\n{text}\n\n"
                f"👉 If the question is about SQL, write a valid SQL query that answers it, using best practices and common table names.\n"
                f"👉 If the question is about Python, write clean and efficient Python code.\n"
                f"👉 If the question is general (non-technical), give a professional and concise answer.\n"
                f"💡 Respond with only the answer — either the SQL code or the final answer — without explanations or extra formatting."
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