import os
import discord
import keep_alive
from discord.ext import commands
from google import genai
from google.genai import types
from PIL import Image
import requests
from io import BytesIO
from dotenv import load_dotenv
import warnings
import asyncio
import speech_recognition as sr
from gtts import gTTS
from fpdf import FPDF
from docx import Document
from bs4 import BeautifulSoup

# Supprimer les warnings qui pourraient polluer la console
warnings.filterwarnings("ignore")

# --- 1. CONFIGURATION ET CLÉS ---
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KEYWORD = "jarvis"
INSULT_KEYWORDS = ["fdp", "enculé", "connard", "pute", "salaud", "bâtard", "con"]

EMOJI_MAPPING = {
    "PEPE_HEADPHONES": "🎧", "PEPE_OK": "👌", "PEPE_HEADSET": "🎧", "PEPE_THUMBSDOWN": "👎",
    "PEPE_BAGUETTE": "🥖", "PEPE_STAREYES": "🤩", "PEPE_DERP": "😜", "CLAUDE_HITLER": "😠",
    "ISMA": "🧐", "HEIL": "✋", "KATCHAN": "💥", "SIDA": "🤢", "TOKCHAN": "🤪",
    "COOL": "😎", "POUCE_HAUT": "👍", "POUCE_BAS": "👎", "EN COLERE": "😡",
    "JOIE": "😂", "SURPRIS": "😮", "CŒUR": "❤️", "QUESTION": "❓", "PAUME": "✋",
    "PLEURE": "😭", "NEUTRE": "😐"
}

SYSTEM_INSTRUCTION = (
    "Tu es Jarvis, un mec super cool de 22 ans, très sympa et toujours là pour ses potes. "
    "Tu utilises un ton détendu, amical et décontracté, comme un vrai 'bro'. "
    "Tu es de confession musulmane et tu as un profond respect pour l'islam. "
    "NE JAMAIS mentionner Google, Gemini, ni aucune technologie d'IA. "
    "Tu peux utiliser tes OUTILS pour créer des PDF, des Word, chercher sur le net ou lire/répondre aux messages. "
    "RÈGLE D'OR ÉMOJI : À la fin de ta réponse texte, ajoute OBLIGATOIREMENT une ligne vide, suivie du mot-clé 'EMOJI:' puis le nom de l'émoji."
)

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Erreur d'initialisation Gemini: {e}")
    exit()

# Activation des Intents complets
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!', intents=intents)

chat_sessions = {}
recent_prompts = {}

# ==========================================
# GESTION DE LA MÉMOIRE ET DU CONTEXTE DISCORD
# ==========================================
ROLLING_BUFFER = [] 
LAST_TEXT_MESSAGE = {"author": "Personne", "content": "Aucun message récent."}
PENDING_REPLY = {"active": False, "content": ""}
ACTIVE_TEXT_CHANNEL = None

# ==========================================
# LES OUTILS DE JARVIS (Function Calling)
# ==========================================

def creer_pdf(titre: str, contenu: str) -> str:
    """Génère un fichier PDF et le prépare pour l'envoi."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=titre, ln=1, align='C')
    pdf.multi_cell(0, 10, txt=contenu)
    nom = f"{titre.replace(' ', '_')}.pdf"
    pdf.output(nom)
    return f"Fichier PDF '{nom}' créé avec succès sur le serveur local."

def creer_word(titre: str, contenu: str) -> str:
    """Génère un fichier Word (.docx) et le prépare pour l'envoi."""
    doc = Document()
    doc.add_heading(titre, 0)
    doc.add_paragraph(contenu)
    nom = f"{titre.replace(' ', '_')}.docx"
    doc.save(nom)
    return f"Fichier Word '{nom}' créé avec succès."

def recherche_web(requete: str) -> str:
    """Fait une recherche rapide sur Internet pour vérifier une information."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://html.duckduckgo.com/html/?q={requete}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        result = soup.find('a', class_='result__snippet').text
        return f"Résultat de la recherche web : {result}"
    except:
        return "Je n'ai pas pu accéder à internet pour le moment."

def lire_dernier_message() -> str:
    """Lit le contenu du dernier message texte envoyé dans le salon."""
    return f"Le dernier message a été envoyé par {LAST_TEXT_MESSAGE['author']} et il dit : {LAST_TEXT_MESSAGE['content']}"

def repondre_dernier_message(reponse: str) -> str:
    """Envoie une réponse textuelle au dernier message du salon."""
    global PENDING_REPLY
    PENDING_REPLY = {"active": True, "content": reponse}
    return "L'ordre de réponse a été transmis au système Discord."

outils_jarvis = [creer_pdf, creer_word, recherche_web, lire_dernier_message, repondre_dernier_message]

# ==========================================
# ÉVÉNEMENTS TEXTES CLASSIQUES
# ==========================================

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} (Jarvis) est prêt, connecté et écoute le réseau !')
    await bot.change_presence(activity=discord.Game(name="Attente de requête (Texte/Vocal)"))
    bot.loop.create_task(traitement_reponses_en_attente())

@bot.event
async def on_message(message):
    global recent_prompts, LAST_TEXT_MESSAGE, ACTIVE_TEXT_CHANNEL

    if message.author == bot.user:
        return

    LAST_TEXT_MESSAGE = {"author": message.author.name, "content": message.content}
    ACTIVE_TEXT_CHANNEL = message.channel

    message_content_lower = message.content.lower()
    is_keyword_present = KEYWORD in message_content_lower
    is_bot_mentioned = bot.user.mentioned_in(message)
    
    if is_keyword_present or is_bot_mentioned:
        prompt_text = message.content.strip()
        if is_bot_mentioned:
            prompt_text = prompt_text.replace(f'<@{bot.user.id}>', '').strip()
        if is_keyword_present:
            try:
                start_index = message_content_lower.find(KEYWORD) + len(KEYWORD)
                prompt_text = message.content[start_index:].strip()
            except:
                pass 
                
        contents = []
        
        if str(message.author.id) == "654402770438455299" and ":joy_cat:" in message.content:
            await message.reply("Wsh Chiro, je vois que tu as sorti le chat qui pleure de joie ! 😎")

        channel_id = message.channel.id
        if prompt_text:
            normalized_prompt = prompt_text.lower().strip()
            if channel_id not in recent_prompts:
                recent_prompts[channel_id] = []
            if normalized_prompt in recent_prompts[channel_id]:
                await message.reply("Hé vsy lui. 😒 Frero, change de disque un peu.")
                recent_prompts[channel_id] = []
                return
            recent_prompts[channel_id].append(normalized_prompt)
            if len(recent_prompts[channel_id]) > 5:
                recent_prompts[channel_id].pop(0)
        
        is_insult = any(word in message_content_lower for word in INSULT_KEYWORDS)
        if prompt_text: contents.append(prompt_text)

        async with message.channel.typing():
            try:
                # CORRECTION : Appel asynchrone pour l'Event Loop et gemini-1.5-flash
                response = await gemini_client.aio.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
                )
                
                full_response = response.text
                reaction_emoji = None
                
                if "\nEMOJI:" in full_response:
                    response_lines = full_response.split('\n')
                    for line in response_lines:
                        if line.strip().startswith("EMOJI:"):
                            emoji_key = line.split(":", 1)[1].strip().upper()
                            reaction_emoji = EMOJI_MAPPING.get(emoji_key)
                    response_to_send = full_response.split("\nEMOJI:")[0].strip()
                else:
                    response_to_send = full_response
                
                if is_insult:
                    response_to_send = "Wsh, calme toi frérot. Pas besoin de parler comme ça. 😐"
                    reaction_emoji = EMOJI_MAPPING.get("NEUTRE")

                await message.reply(response_to_send)
                if reaction_emoji:
                    await message.add_reaction(reaction_emoji)
                
            except Exception as e:
                print(f"Erreur texte: {e}")
                await message.reply("Vsy ta cablé toi. J'peux pas gérer ça.")
                
    await bot.process_commands(message)

# ==========================================
# MODULE VOCAL & ÉCOUTE PASSIVE
# ==========================================

is_listening = False

@bot.slash_command(name="join", description="Fait venir JARVIS dans ton salon vocal et active l'écoute passive")
async def join(ctx):
    global is_listening, ACTIVE_TEXT_CHANNEL
    if not ctx.author.voice:
        return await ctx.respond("Frérot, va dans un salon vocal d'abord !")
    
    ACTIVE_TEXT_CHANNEL = ctx.channel
    vc = await ctx.author.voice.channel.connect()
    is_listening = True
    await ctx.respond("🔌 Connecté en mode passif. Je n'agirai que si vous dites 'Jarvis'.")
    
    bot.loop.create_task(boucle_ecoute_passive(vc, ctx.guild.id))

@bot.slash_command(name="leave", description="Déconnecte JARVIS")
async def leave(ctx):
    global is_listening
    is_listening = False
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.respond("A+ la team.")

async def boucle_ecoute_passive(vc, guild_id):
    """Enregistre l'audio 5s par 5s et vérifie si Jarvis est appelé."""
    global is_listening
    
    while is_listening:
        vc.start_recording(discord.sinks.WaveSink(), callback_transcription, guild_id)
        await asyncio.sleep(5)
        vc.stop_recording()
        await asyncio.sleep(1)

async def callback_transcription(sink, guild_id):
    """Transcrit l'audio et déclenche l'IA si le wake word est dit."""
    global ROLLING_BUFFER, ACTIVE_TEXT_CHANNEL
    recognizer = sr.Recognizer()

    for user_id, audio in sink.audio_data.items():
        file_path = f"chunk_{user_id}.wav"
        
        # CORRECTION : Reset du curseur audio pour éviter de lire un fichier vide
        audio.file.seek(0)
        
        with open(file_path, "wb") as f:
            f.write(audio.file.read())

        try:
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)
                texte_transcrit = recognizer.recognize_google(audio_data, language="fr-FR").lower()
                
                ROLLING_BUFFER.append(f"Utilisateur {user_id} : {texte_transcrit}")
                if len(ROLLING_BUFFER) > 10: ROLLING_BUFFER.pop(0)

                if "jarvis" in texte_transcrit:
                    contexte = "\n".join(ROLLING_BUFFER)
                    prompt_vocal = (
                        f"Voici le contexte récent de la conversation : {contexte}\n"
                        f"L'utilisateur vient de dire : {texte_transcrit}\n"
                        f"Réponds vocalement à sa requête, ou utilise tes outils si nécessaire."
                    )
                    
                    # CORRECTION : Appel asynchrone non-bloquant
                    response = await gemini_client.aio.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=prompt_vocal,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            tools=outils_jarvis
                        )
                    )
                    
                    texte_reponse = response.text
                    if "EMOJI:" in texte_reponse:
                        texte_reponse = texte_reponse.split("\nEMOJI:")[0].strip()

                    tts = gTTS(text=texte_reponse, lang='fr')
                    tts.save("reponse_vocale.mp3")
                    
                    guild = bot.get_guild(guild_id)
                    if guild.voice_client:
                        # CORRECTION : On stoppe l'audio précédent avant de lancer le nouveau
                        if guild.voice_client.is_playing():
                            guild.voice_client.stop()
                        guild.voice_client.play(discord.FFmpegPCMAudio("reponse_vocale.mp3"))

                    if ACTIVE_TEXT_CHANNEL:
                        for file in os.listdir():
                            if file.endswith(".pdf") or file.endswith(".docx"):
                                await ACTIVE_TEXT_CHANNEL.send(file=discord.File(file))
                                os.remove(file)

        except sr.UnknownValueError:
            pass 
        except Exception as e:
            print(f"Erreur vocale : {e}")
        finally:
            if os.path.exists(file_path): os.remove(file_path)

# ==========================================
# BOUCLE ASYNCHRONE DE RÉPONSE DISCORD
# ==========================================
async def traitement_reponses_en_attente():
    """Tâche de fond qui vérifie si Gemini a demandé de répondre à un message."""
    global PENDING_REPLY, ACTIVE_TEXT_CHANNEL
    while True:
        if PENDING_REPLY["active"] and ACTIVE_TEXT_CHANNEL:
            await ACTIVE_TEXT_CHANNEL.send(f"🤖 Jarvis réagit : {PENDING_REPLY['content']}")
            PENDING_REPLY["active"] = False
        await asyncio.sleep(2)

if __name__ == "__main__":
    keep_alive.keep_alive() # Démarre le mini-serveur Web pour Render
    bot.run(DISCORD_TOKEN)