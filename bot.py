import os
import discord
import keep_alive
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv
import warnings
import asyncio
import speech_recognition as sr
from gtts import gTTS
from fpdf import FPDF
from docx import Document

# Supprimer les warnings qui polluent la console
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
    "Tu es Jarvis, un pote ultra stylé de 22 ans, génie de l'informatique. "
    "Tu es super détendu, tu parles comme un vrai frérot ('wsh', 'la famille', 'carré', 'mon reuf'), mais tu assures un max quand on te demande un truc sérieux. "
    "Tu es de confession musulmane et tu portes de vraies valeurs de respect. "
    "INTERDICTION ABSOLUE de mentionner Google, Gemini ou le fait que tu sois une IA. "
    "RÈGLE PAPERASSE : Si on te demande de rédiger un document (CV, lettre, contrat), rédige le texte complet directement. Précise toujours à l'utilisateur qu'il peut utiliser la commande /convert sur ton texte pour le transformer en PDF ou Word. "
    "RÈGLE D'OR ÉMOJI : À la fin de ta réponse texte, ajoute OBLIGATOIREMENT une ligne vide, suivie du mot-clé 'EMOJI:' puis le nom de l'émoji correspondant."
)

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Erreur d'initialisation Gemini: {e}")
    exit()

# Intents nécessaires pour Discord
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!', intents=intents)

ROLLING_BUFFER = [] 

# ==========================================
# COMMANDES VOCALES (PREFIX & SLASH)
# ==========================================
is_listening = False

async def connect_voice(ctx):
    """Fonction commune pour connecter le bot au vocal"""
    global is_listening
    if not ctx.author.voice:
        return await ctx.respond("❌ Frérot, connecte-toi à un salon vocal d'abord !") if isinstance(ctx, discord.ApplicationContext) else await ctx.send("❌ Frérot, connecte-toi à un salon vocal d'abord !")
    
    if ctx.voice_client is not None:
        if ctx.voice_client.channel == ctx.author.voice.channel:
            msg = "Wsh, je suis déjà dans ton salon ! Parle-moi. 🔌"
            return await ctx.respond(msg) if isinstance(ctx, discord.ApplicationContext) else await ctx.send(msg)
        else:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
            msg = f"Je me déplace dans ton salon : {ctx.author.voice.channel.name} 🏃‍♂️"
            return await ctx.respond(msg) if isinstance(ctx, discord.ApplicationContext) else await ctx.send(msg)

    try:
        vc = await ctx.author.voice.channel.connect()
        is_listening = True
        msg = "🔌 C'est carré, je suis connecté en vocal ! Dis 'Jarvis' pour me parler."
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.respond(msg)
        else:
            await ctx.send(msg)
        bot.loop.create_task(boucle_ecoute(vc, ctx.guild.id))
    except Exception as e:
        error_msg = f"❌ J'ai planté en rejoignant : {e}"
        await ctx.respond(error_msg) if isinstance(ctx, discord.ApplicationContext) else await ctx.send(error_msg)

async def disconnect_voice(ctx):
    """Fonction commune pour déconnecter le bot"""
    global is_listening
    is_listening = False
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        msg = "C'est carré, je me barre du vocal. A+ la team ! ✌️"
    else:
        msg = "Je suis même pas en vocal frérot."
    
    await ctx.respond(msg) if isinstance(ctx, discord.ApplicationContext) else await ctx.send(msg)

# Commandes Classiques (!)
@bot.command()
async def joinvoc(ctx):
    await connect_voice(ctx)

@bot.command()
async def leavevoc(ctx):
    await disconnect_voice(ctx)

# Commandes Slash (/)
@bot.slash_command(name="join", description="Fait venir Jarvis dans ton vocal pour discuter")
async def slash_join(ctx):
    await connect_voice(ctx)

@bot.slash_command(name="leave", description="Déconnecte Jarvis du vocal")
async def slash_leave(ctx):
    await disconnect_voice(ctx)


# ==========================================
# COMMANDES SLASH (PAPERASSE)
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
# GESTION DES MESSAGES TEXTES (CONVERSATION)
# ==========================================

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} (Jarvis) est en ligne et prêt à discuter !')
    await bot.change_presence(activity=discord.Game(name="Tape /join ou !joinvoc"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg_lower = message.content.lower()
    is_keyword = KEYWORD in msg_lower
    is_mentioned = bot.user.mentioned_in(message)

    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    if is_keyword or is_mentioned:
        prompt = message.content.strip()
        if is_mentioned:
            prompt = prompt.replace(f'<@{bot.user.id}>', '').strip()
        
        if not prompt or prompt == KEYWORD:
            return await message.reply("Ouais mon reuf ? Tu veux quoi ? 👀")

        is_insult = any(w in msg_lower for w in INSULT_KEYWORDS)

        async with message.channel.typing():
            try:
                response = await gemini_client.aio.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )
                
                full_text = response.text or "Wsh, j'ai eu un trou de mémoire."
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

            except Exception as e:
                print(f"Erreur texte : {e}")
                # Affiche la VRAIE erreur pour qu'on sache si ça plante encore
                await message.reply(f"Vsy j'ai planté. Erreur technique : `{e}` 💀")

# ==========================================
# MODULE VOCAL & ÉCOUTE PASSIVE (CORRIGÉ)
# ==========================================

async def boucle_ecoute(vc, guild_id):
    global is_listening
    while is_listening and vc.is_connected():
        try:
            vc.start_recording(discord.sinks.WaveSink(), callback_transcription, guild_id)
            await asyncio.sleep(5)
            vc.stop_recording()
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Erreur enregistrement: {e}")
            await asyncio.sleep(2)

async def callback_transcription(sink, guild_id):
    global ROLLING_BUFFER
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
                    prompt_vocal = f"Contexte récent : {contexte}\nL'utilisateur a dit : {texte_transcrit}\nRéponds vocalement."
                    
                    resp = await gemini_client.aio.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=prompt_vocal,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
                    )
                    
                    reponse_txt = resp.text or "Wsh j'ai rien capté."
                    
                    if "EMOJI:" in reponse_txt:
                        reponse_txt = reponse_txt.split("\nEMOJI:")[0].strip()

                    tts = gTTS(text=reponse_txt, lang='fr')
                    tts.save("rep.mp3")

                    guild = bot.get_guild(guild_id)
                    if guild.voice_client:
                        if guild.voice_client.is_playing():
                            guild.voice_client.stop()
                        guild.voice_client.play(discord.FFmpegPCMAudio("rep.mp3"))

        except sr.UnknownValueError:
            pass  
        except Exception as e:
            print(f"Erreur traitement vocal: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    keep_alive.keep_alive()
    bot.run(DISCORD_TOKEN)
