# 🎤 Real-Time  Q&A Assistant (Whisper + Gemini)

This project is a real-time speech-to-answer assistant that listens to your voice, transcribes it with OpenAI Whisper, and responds using Google Gemini API — all through a live, minimal overlay interface.

---

## 🚀 Features

- 🎙️ Real-time voice recording (`sounddevice`)
- 🧠 Transcription using [OpenAI Whisper](https://github.com/openai/whisper)
- 🤖 Intelligent response generation with Gemini 1.5 Flash
- 🪟 Live overlay window with `tkinter`
- ⌨️ Keyboard shortcuts:  
  - `F9`: Start recording  
  - `K`: Stop and send to Gemini  
  - `ESC`: Exit

---

## 🛠 Installation

1. **Clone the repository:**

```bash
git clone https://github.com/enesozyaramiss/Msupp.git
cd Msupp

python -m venv venv310
.\venv310\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

Create a .env file in the root directory with the following content:
GEMINI_API_KEY=your_api_key_here

python Main.py

## 📝 License

MIT License.
