import os
import uuid
from flask import Flask, request, jsonify, url_for
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv
import google.generativeai as genai
from gtts import gTTS

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

app = Flask(__name__)

# Ensure static/audio directory exists for TTS files
AUDIO_DIR = os.path.join(app.static_folder, 'audio') if app.static_folder else os.path.join(app.root_path, 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

def get_ai_response(text):
    prompt = f"""
    You are a professional, empathetic medical assistant named ElderCareGPT.
    A patient just described their symptoms: "{text}"
    Respond in 2-3 short, clear sentences. State the likely medical condition (if any), 
    provide simple care tips, and mention any critical warning signs where they should seek emergency care.
    Use professional medical terminology but keep it easy to understand. Try not to use asterisks or markdown formatting.
    If it's severe, advise them to contact a healthcare provider immediately.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        # Clean up any potential markdown for TTS friendliness
        clean_text = response.text.strip().replace('*', '').replace('#', '')
        return clean_text
    except Exception as e:
        print(f"Error calling Gemini: {e}", flush=True)
        return "I'm having trouble connecting to my medical database. Please consult a healthcare provider."

def generate_tts(text):
    try:
        tts = gTTS(text, lang='en')
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        tts.save(filepath)
        return filename
    except Exception as e:
        print(f"Error generating TTS: {e}")
        return None

@app.route('/')
def index():
    return "ElderCareGPT Server is running! Try visiting /api/symptoms to see the API in action.", 200

@app.route('/whatsapp', methods=['POST'])
def whatsapp_handler():
    incoming = request.values.get('Body', '').strip()
    media_count = int(request.values.get('NumMedia', '0'))
    response = MessagingResponse()

    # If the user sends a voice note, we can't easily transcribe it right now without Whisper.
    if media_count > 0:
        response.message(
            "I received your voice message. However, I can currently only read text messages. "
            "Please type out your symptoms for guidance."
        )
        return str(response)

    if not incoming:
        response.message("Welcome to ElderCareGPT. Send me your symptoms and I will give you professional guidance.")
        return str(response)

    # 1. Get AI Text
    guidance = get_ai_response(incoming)
    
    # 2. Get AI Voice
    msg = response.message(guidance)
    audio_filename = generate_tts(guidance)
    
    if audio_filename:
        # Construct the full URL to the audio file
        audio_url = request.host_url.rstrip('/') + url_for('static', filename=f'audio/{audio_filename}')
        msg.media(audio_url)

    return str(response)

@app.route('/voice', methods=['POST'])
def voice_handler():
    resp = VoiceResponse()
    user_speech = request.values.get('SpeechResult', '').strip()

    if not user_speech:
        resp.say('Hello, welcome to Elder Care G P T. Please describe your symptoms after the tone.')
        resp.record(max_length=15, transcribe=True, transcribe_callback='/voice')
        return str(resp)

    # 1. Get AI Text
    guidance = get_ai_response(user_speech)
    
    # 2. Say it back
    resp.say(guidance)
    return str(resp)

@app.route('/api/symptoms', methods=['GET','POST'])
def symptom_api():
    if request.method == 'GET':
        return jsonify({
            'message': 'Send a POST request with JSON {"text":"your symptoms"}.',
            'sample': {'text': 'I feel dizzy and have a headache.'}
        })

    data = request.get_json(force=True, silent=True) or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'text is required'}), 400
        
    guidance = get_ai_response(text)
    audio_filename = generate_tts(guidance)
    audio_url = request.host_url.rstrip('/') + url_for('static', filename=f'audio/{audio_filename}') if audio_filename else None
    
    return jsonify({
        'guidance': guidance,
        'audio_url': audio_url
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
