import os
import uuid
from flask import Flask, request, jsonify, url_for
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv
import google.generativeai as genai
from gtts import gTTS
import requests
import time

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

app = Flask(__name__)

# Ensure static/audio and uploads directory exist
AUDIO_DIR = os.path.join(app.static_folder, 'audio') if app.static_folder else os.path.join(app.root_path, 'static', 'audio')
UPLOAD_DIR = '/tmp' if os.path.exists('/tmp') else os.path.join(app.root_path, 'uploads')
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

def download_twilio_media(media_url):
    """Securely downloads media from Twilio using Account SID and Auth Token."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    print(f"Attempting download from: {media_url}", flush=True)
    print(f"Credentials Check - SID: {sid[:4] if sid else 'None'}... Token: {token[:4] if token else 'None'}...", flush=True)

    try:
        # First, try with authentication (required if Twilio project settings are restrictive)
        response = requests.get(
            media_url, 
            auth=(sid, token),
            stream=True,
            timeout=15
        )
        
        print(f"Twilio Download Initial Status: {response.status_code}", flush=True)
        
        # If it failed with 401 or similar, try without auth (if media is public)
        if response.status_code != 200:
            print("Auth failed, attempting without credentials...", flush=True)
            response = requests.get(media_url, stream=True, timeout=15)
            print(f"Unauthenticated Download Status: {response.status_code}", flush=True)

        if response.status_code == 200:
            # Detect extension from Content-Type
            content_type = response.headers.get('Content-Type', '')
            ext = 'ogg' # Default for WhatsApp
            if 'mpeg' in content_type: ext = 'mp3'
            elif 'amr' in content_type: ext = 'amr'
            
            filename = f"user_{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            print(f"Successfully downloaded to {filepath} ({file_size} bytes)", flush=True)
            return filepath
        else:
            print(f"Failed all download attempts. Final Status: {response.status_code}", flush=True)
    except Exception as e:
        print(f"Error during media download: {e}", flush=True)
    return None

def get_ai_response(text=None, audio_path=None):
    """Generates professional medical response from either text or audio input."""
    base_prompt = """
    You are a professional, empathetic medical assistant named ElderCareGPT.
    If the input is symptoms (text or audio), respond in 2-3 short, clear sentences. 
    State the likely medical condition (if any), provide simple care tips, and mention 
    any critical warning signs where they should seek emergency care.
    Use professional medical terminology but keep it easy to understand. Try not to use asterisks or markdown formatting.
    If symptoms are severe, advise immediate contact with a healthcare provider.
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        if audio_path:
            # Upload the file to Gemini's File API
            uploaded_file = genai.upload_file(path=audio_path)
            # Wait for file to be processed (usually fast for audio)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)
            
            response = model.generate_content([base_prompt, uploaded_file])
            # Optional: delete file from Gemini storage after use
            genai.delete_file(uploaded_file.name)
        else:
            response = model.generate_content(f"{base_prompt}\nPatient input: {text}")
        
        clean_text = response.text.strip().replace('*', '').replace('#', '')
        print(f"AI Guidance Result: {clean_text}", flush=True)
        return clean_text
    except Exception as e:
        import traceback
        print(f"Error calling Gemini: {e}", flush=True)
        traceback.print_exc()
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

    # If the user sends a voice note / audio
    if media_count > 0:
        media_url = request.values.get('MediaUrl0')
        media_type = request.values.get('MediaContentType0', '')
        
        if 'audio' in media_type:
            audio_file = download_twilio_media(media_url)
            if audio_file:
                guidance = get_ai_response(audio_path=audio_file)
                # Cleanup local file after AI processing
                os.remove(audio_file)
            else:
                guidance = "I received your voice note but couldn't download it. Please try typing your symptoms."
        else:
            guidance = "I currently only support text or voice notes. Please send a description of your symptoms."
            
        # Send text response and voice response as usual
        msg = response.message(guidance)
        audio_filename = generate_tts(guidance)
        if audio_filename:
            # Force HTTPS for Render/Twilio compatibility
            base_url = request.host_url.replace('http://', 'https://').rstrip('/')
            audio_url = base_url + url_for('static', filename=f'audio/{audio_filename}')
            print(f"Sending Media URL to Twilio: {audio_url}", flush=True)
            msg.media(audio_url)
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
        # Force HTTPS for Render/Twilio compatibility
        base_url = request.host_url.replace('http://', 'https://').rstrip('/')
        audio_url = base_url + url_for('static', filename=f'audio/{audio_filename}')
        print(f"Sending Media URL to Twilio: {audio_url}", flush=True)
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
