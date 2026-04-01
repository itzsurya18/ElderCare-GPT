# ElderCareGPT

ElderCareGPT is a smartphone-friendly elderly healthcare assistant inspired by Alexa Care Hub. It supports WhatsApp text and voice notes, provides simple clinical guidance on chronic conditions (diabetes, blood pressure, arthritis), suggests self-care actions, warning signs, and when to seek medical help.

## Features
- WhatsApp bot (Twilio) for text and media input
- Basic voice call endpoint (Twilio Voice)
- Chronic condition rule-based guidance
- Easy-to-understand language for caregivers and elderly users
- Self-care advice, warning signs, and escalation prompts

## Setup
1. Create a Python environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` (optional) with Twilio configuration:
   ```ini
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   ```
4. Start app:
   ```bash
   python app.py
   ```

## Twilio WhatsApp setup
- Configure WhatsApp sandbox with an incoming message webhook to:
  `https://<your public host>/whatsapp`
- For voice calls, point Twilio voice webhook to: `https://<your public host>/voice`

## Usage
- Text example: `My blood pressure is high and I have a headache.`
- Audio: send an audio note via WhatsApp; bot asks for text fallback (extension for speech-to-text integration)
- Voice call: speak symptoms and get guidance read back

## Extension ideas
- Add OpenAI or local LLM integration for free-form conversational guidance.
- Add speech-to-text transcription for WhatsApp voice notes via Whisper or Twilio Transcription.
- Add user profile storage and medication reminders.
