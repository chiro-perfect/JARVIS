import os
import discord
import keep_alive
from discord.ext import commands
from google import genai
from google.genai import types
import requests
from dotenv import load_dotenv
import warnings
import asyncio
import speech_recognition as sr
from gtts import gTTS
from fpdf import FPDF
from docx import Document
from bs4 import BeautifulSoup

# Supprimer les warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ET CLÉS ---
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
    "Tu es Jarvis, un pote ultra stylé de 22 ans, génie de l'informatique et pro de la paperasse administrative (CV, lettres, contrats, résumés). "
    "Tu es super détendu, tu parles comme un vrai frérot ('wsh', 'la famille', 'carré'), mais tu assures un max. "
    "Tu es de confession musulmane et tu portes de vraies valeurs de respect. "
    "INTERDICTION ABSOLUE de mentionner Google, Gemini ou le fait que tu sois une IA. "
    "Tu peux créer des fichiers PDF, Word, chercher sur le web, et rédiger n'importe quel document administratif. "
    "RÈGLE D'OR ÉMOJI : À la fin de ta réponse texte, ajoute OBLIGATOIREMENT une ligne vide, suivie du mot-clé 'EMOJI:' puis le nom de l'émoji correspondant."
)

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Erreur d'initialisation Gemini: {e}")
    exit()

# Intents
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!', intents=intents)

ROLLING_BUFFER = [] 
ACTIVE_TEXT_CHANNEL = None

# ==========================================
# OUTILS DE JARVIS (Function Calling)
# ==========================================

def creer_pdf(titre: str, contenu: str) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=titre, ln=1, align='C')
    pdf.multi_cell(0, 10, txt=contenu)
    nom = f"{titre.replace(' ', '_')}.pdf"
    pdf.output(nom)
    return f"Fichier PDF '{nom}' généré avec brio !"

def creer_word(titre: str, contenu: str) -> str:
    doc = Document()
    doc.add_heading(titre, 0)
    doc.add_paragraph(contenu)
    nom = f"{titre.replace(' ', '_')}.docx"
    doc.save(nom)
    return f"Fichier Word '{nom}' prêt à l'emploi !"

def recherche_web(requete: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://html.duckduckgo.com/html/?q={requete}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        result = soup.find('a', class_='result__snippet').text
        return f"Info trouvée sur le net : {result}"
    except:
        return "J'ai cherché mais le net fait des siennes frérot."

outils_jarvis = [creer_pdf, creer_word, recherche_web]

# ==========================================
# COMMANDES SLASH (PAPERASSE & CONVERSION)
# ==========================================

@bot.slash_command(name="convert", description="Convertit ton texte directement en PDF ou en Word propre")
async def convert(ctx, format: str, titre: str, contenu: str):
    await ctx.defer()
    fmt = format.strip().lower()
    if fmt not in ["pdf", "word"]:
        return await ctx.respond("Frérot, choisis bien entre 'pdf' ou 'word' dans le format ! ❌", ephemeral=True)

    nom_fichier = titre.replace(' ', '_')
    if fmt == "pdf":
        nom_fichier += ".pdf"
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=titre, ln=1, align='C')
        pdf.multi_cell(0, 10, txt=contenu)
        pdf.output(nom_fichier)
    else:
        nom_fichier += ".docx"
        doc = Document()
        doc.add_heading(titre, 0)
        doc.add_paragraph(contenu)
        doc.save(nom_fichier)

    await ctx.respond(f"Carré la famille ! Ton fichier **{nom_fichier}** est prêt 👇", file=discord.File(nom_fichier))
    os.remove(nom_fichier)

@bot.slash_command(name="pdf", description="Génère un fichier PDF ultra rapidement")
async def slash_pdf(ctx, titre: str, contenu: str):
    await ctx.defer()
    nom = f"{titre.replace(' ', '_')}.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=titre, ln=1, align='C')
    pdf.multi_cell(0, 10, txt=contenu)
    pdf.output(nom)
    await ctx.respond(f"Tiens poto, ton PDF '{titre}' est bouclé ! 📄", file=discord.File(nom))
    os.remove(nom)

@bot.slash_command(name="word", description="Génère un fichier Word (.docx) rapidement")
async def slash_word(ctx, titre: str, contenu: str):
    await ctx.defer()
    nom = f"{titre.replace(' ', '_')}.docx"
    doc = Document()
    doc.add_heading(titre, 0)
    doc.add_paragraph(contenu)
    doc.save(nom)
    await ctx.respond(f"Propre ! Ton Word '{titre}' est prêt. 📝", file=discord.File(nom))
    os.remove(nom)

# ==========================================
# GESTION DES MESSAGES TEXTES
# ==========================================

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} (Jarvis) est en ligne et prêt !')
    await bot.change_presence(activity=discord.Game(name="/join pour le vocal !"))

@bot.event
async def on_message(message):
    global ACTIVE_TEXT_CHANNEL

    if message.author == bot.user:
        return

    ACTIVE_TEXT_CHANNEL = message.channel
    msg_lower = message.content.lower()
    is_keyword = KEYWORD in msg_lower
    is_mentioned = bot.user.mentioned_in(message)

    if is_keyword or is_mentioned:
        prompt = message.content.strip()
        if is_mentioned:
            prompt = prompt.replace(f'<@{bot.user.id}>', '').strip()
        
        # Sécurité si le message est juste "jarvis"
        if not prompt or prompt == KEYWORD:
            return await message.reply("Ouais mon reuf ? Tu veux quoi ? 👀")

        is_insult = any(w in msg_lower for w in INSULT_KEYWORDS)

        async with message.channel.typing():
            try:
                response = await gemini_client.aio.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=outils_jarvis
                    )
                )
                
                full_text = response.text or "Wsh, j'ai buggé une sec."
                emoji_key = "COOL"
                
                if "\nEMOJI:" in full_text:
                    parts = full_text.split("\nEMOJI:")
                    full_text = parts[0].strip()
                    ekey = parts[1].strip().upper()
                    emoji_key = ekey if ekey in EMOJI_MAPPING else "COOL"

                if is_insult:
                    full_text = "Wsh, calme tes nerfs frérot, on gère ça proprement. 😐"
                    emoji_key = "NEUTRE"

                await message.reply(full_text)
                if emoji_key in EMOJI_MAPPING:
                    await message.add_reaction(EMOJI_MAPPING[emoji_key])

                for file in os.listdir():
                    if file.endswith(".pdf") or file.endswith(".docx"):
                        await message.channel.send("Tiens, voilà le document demandé poto 👇", file=discord.File(file))
                        os.remove(file)

            except Exception as e:
                print(f"Erreur texte : {e}")
                await message.reply("Vsy t'as cablé, mon cerveau a lâché. 💀")

    await bot.process_commands(message)

# ==========================================
# MODULE VOCAL & ÉCOUTE PASSIVE (CORRIGÉ & ROBUSTE)
# ==========================================

is_listening = False

@bot.slash_command(name="join", description="Fait venir Jarvis dans ton vocal pour discuter")
async def join(ctx):
    global is_listening, ACTIVE_TEXT_CHANNEL
    
    if not ctx.author.voice:
        return await ctx.respond("Frérot, connecte-toi à un salon vocal d'abord ! 🎧")
    
    ACTIVE_TEXT_CHANNEL = ctx.channel

    # Si le bot est déjà connecté
    if ctx.voice_client is not None:
        if ctx.voice_client.channel == ctx.author.voice.channel:
            return await ctx.respond("Wsh, je suis déjà dans ton salon ! Parle-moi. 🔌")
        else:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
            return await ctx.respond(f"Je me déplace dans ton salon : {ctx.author.voice.channel.name} 🏃‍♂️")

    try:
        vc = await ctx.author.voice.channel.connect()
        is_listening = True
        await ctx.respond("🔌 C'est carré, je suis connecté en vocal ! Dis 'Jarvis' pour me parler.")
        bot.loop.create_task(boucle_ecoute(vc, ctx.guild.id))
    except discord.errors.Forbidden:
        await ctx.respond("❌ Je n'ai pas la permission de rejoindre ce salon ! Donne à mon rôle la perm 'Se connecter'.")
    except Exception as e:
        print(f"Erreur connexion vocal: {e}")
        await ctx.respond(f"❌ J'ai planté en rejoignant : {e}")

@bot.slash_command(name="leave", description="Déconnecte Jarvis du vocal")
async def leave(ctx):
    global is_listening
    is_listening = False
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.respond("Je me barre du vocal. A+ la team ! ✌️")
    else:
        await ctx.respond("Je suis même pas en vocal frérot.")

async def boucle_ecoute(vc, guild_id):
    global is_listening
    while is_listening and vc.is_connected():
        try:
            vc.start_recording(discord.sinks.WaveSink(), callback_transcription, guild_id)
            await asyncio.sleep(5)
            vc.stop_recording()
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Erreur dans la boucle d'enregistrement : {e}")
            await asyncio.sleep(2)

async def callback_transcription(sink, guild_id):
    global ROLLING_BUFFER, ACTIVE_TEXT_CHANNEL
    recognizer = sr.Recognizer()

    for user_id, audio in sink.audio_data.items():
        path = f"chunk_{user_id}.wav"
        audio.file.seek(0)
        with open(path, "wb") as f:
            f.write(audio.file.read())

        try:
            with sr.AudioFile(path) as source:
                audio_data = recognizer.record(source)
                texte_transcrit = recognizer.recognize_google(audio_data, language="fr-FR").lower()
                
                ROLLING_BUFFER.append(f"User : {texte_transcrit}")
                if len(ROLLING_BUFFER) > 10: ROLLING_BUFFER.pop(0)

                if "jarvis" in texte_transcrit:
                    contexte = "\n".join(ROLLING_BUFFER)
                    prompt_vocal = f"Contexte récent : {contexte}\nL'utilisateur a dit : {texte_transcrit}\nRéponds vocalement en mode poto."
                    
                    resp = await gemini_client.aio.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=prompt_vocal,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, tools=outils_jarvis)
                    )
                    
                    reponse_txt = resp.text or "Wsh j'ai rien capté."
                    
                    # Correction vitale de la gestion des emojis pour le vocal
                    if "EMOJI:" in reponse_txt:
                        reponse_txt = reponse_txt.split("\nEMOJI:")[0].strip()

                    tts = gTTS(text=reponse_txt, lang='fr')
                    tts.save("rep.mp3")

                    guild = bot.get_guild(guild_id)
                    if guild.voice_client:
                        if guild.voice_client.is_playing():
                            guild.voice_client.stop()
                        guild.voice_client.play(discord.FFmpegPCMAudio("rep.mp3"))

                    for file in os.listdir():
                        if (file.endswith(".pdf") or file.endswith(".docx")) and ACTIVE_TEXT_CHANNEL:
                            await ACTIVE_TEXT_CHANNEL.send("Tiens le document généré en vocal 👇", file=discord.File(file))
                            os.remove(file)

        except sr.UnknownValueError:
            pass  # Silence normal
        except Exception as e:
            print(f"Erreur pendant le traitement vocal: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    keep_alive.keep_alive()
    bot.run(DISCORD_TOKEN)
