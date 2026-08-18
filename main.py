import os
import discord
from discord import app_commands
import requests
import json

# Configuration Hugging Face (GRATUIT EN LIGNE)
HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY")  # https://huggingface.co/settings/tokens
HF_MODEL = "HuggingFaceH4/zephyr-7b-beta"  # Bon en français
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Commandes slash synchronisées.")

bot = MyBot()
game_sessions = {}

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print(f"🤖 Modèle utilisé: {HF_MODEL}")

def query_huggingface(prompt: str) -> str:
    """Requête à Hugging Face Inference API"""
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 50,
            "temperature": 0.3
        }
    }
    
    API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        print(f"[HF-STATUS] Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"[HF-REPONSE] Brute: {result}")
            
            # Le modèle retourne une liste avec le texte généré
            if isinstance(result, list) and len(result) > 0:
                texte = result[0].get("generated_text", "")
                return texte.strip()
            else:
                return ""
        else:
            print(f"[HF-ERREUR] Statut {response.status_code}: {response.text}")
            return ""
            
    except Exception as e:
        print(f"[ERREUR] Requête HF échouée: {e}")
        return ""

@bot.tree.command(name="ping", description="Vérifie si le bot et l'IA fonctionnent.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    ai_status = "❌ HF ne répond pas"
    try:
        reponse = query_huggingface("Réponds juste 'Pong'")
        if reponse:
            ai_status = f"✅ HF OK (réponse: {reponse[:30]}...)"
        else:
            ai_status = "❌ Réponse vide de HF"
    except Exception as e:
        ai_status = f"❌ Erreur: {str(e)[:50]}"

    await interaction.followup.send(f"Pong 🏓!\nStatut Hugging Face: **{ai_status}**")

async def generer_premier_mot():
    """L'IA génère un mot aléatoire"""
    prompt = "Propose UN SEUL mot petit (atome, grain, cellule, etc). Juste le mot, rien d'autre."
    
    reponse = query_huggingface(prompt)
    print(f"[IA-GENERER] Réponse brute: '{reponse}'")
    
    if reponse:
        # Nettoyer la réponse (prendre le premier mot)
        mots = reponse.split()
        mot = mots[0].lower().strip(".,!?;:")
        
        if mot and len(mot) > 1:
            print(f"[IA-GENERER] Mot généré: '{mot}'")
            return mot
    
    print(f"[ERREUR] Pas de réponse, fallback à 'atome'")
    return "atome"

@bot.tree.command(name="jeu-grandeur", description="Active/désactive le jeu de la grandeur")
@app_commands.describe(
    statut="Activer ou désactiver",
    salon="Le salon du jeu"
)
@app_commands.choices(statut=[
    app_commands.Choice(name="activé", value="active"),
    app_commands.Choice(name="désactivé", value="desactive")
])
async def jeu_grandeur(interaction: discord.Interaction, statut: app_commands.Choice[str], salon: discord.TextChannel):
    if statut.value == "active":
        premier_mot = await generer_premier_mot()
        
        game_sessions[salon.id] = {
            "active": True,
            "dernier_mot": premier_mot,
            "dernier_joueur": None,
            "historique": [premier_mot]
        }
        await interaction.response.send_message(
            f"✅ Jeu activé dans {salon.mention}!\n"
            f"🚀 Mot de départ: **{premier_mot}**"
        )
    else:
        if salon.id in game_sessions:
            del game_sessions[salon.id]
        await interaction.response.send_message(f"❌ Jeu désactivé dans {salon.mention}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.channel.id not in game_sessions:
        return

    session = game_sessions[message.channel.id]
    if not session["active"]:
        return

    if message.author.id == session["dernier_joueur"]:
        await message.add_reaction("❌")
        await message.channel.send(f"{message.author.mention} Tu ne peux pas jouer deux fois de suite!")
        return

    nouveau_mot = message.content.strip().lower()
    dernier_mot = session["dernier_mot"]
    
    print(f"\n[JEU] Nouveau mot: '{nouveau_mot}' | Précédent: '{dernier_mot}'")

    # Prompt très strict pour la réponse
    prompt = (
        f"Réponds avec UN SEUL mot: OUI ou NON.\n"
        f"Question: '{nouveau_mot}' est-il plus GRAND/PUISSANT que '{dernier_mot}'?\n"
        f"Réponse:"
    )

    reponse_ia = query_huggingface(prompt)
    print(f"[IA-REPONSE] Brute: '{reponse_ia}'")
    
    # Extraire OUI ou NON
    reponse_clean = reponse_ia.upper().strip()
    print(f"[IA-CLEAN] '{reponse_clean}'")
    
    if not reponse_clean:
        await message.channel.send(f"⚠️ Erreur: pas de réponse de l'IA")
        return

    if "OUI" in reponse_clean and "NON" not in reponse_clean:
        print(f"[ACCEPTÉ] '{nouveau_mot}' est valide")
        session["dernier_mot"] = nouveau_mot
        session["dernier_joueur"] = message.author.id
        session["historique"].append(nouveau_mot)
        await message.add_reaction("✅")
        
    else:
        print(f"[REJETÉ] '{nouveau_mot}' n'est pas valide (réponse: {reponse_clean})")
        
        historique_str = " → ".join(session["historique"])
        await message.add_reaction("❌")
        await message.channel.send(
            f"❌ **Perdu!** '{nouveau_mot}' n'est pas supérieur à '{dernier_mot}'\n"
            f"📜 Historique: {historique_str}\n"
            f"💬 Réponse IA: **{reponse_clean}**"
        )
        
        nouveau_premier_mot = await generer_premier_mot()
        session["dernier_mot"] = nouveau_premier_mot
        session["dernier_joueur"] = None
        session["historique"] = [nouveau_premier_mot]
        await message.channel.send(f"🔄 Nouvelle partie! Mot: **{nouveau_premier_mot}**")

print("🤖 Bot Discord - Mode Hugging Face (Gratuit)")
print("📚 Modèle:", HF_MODEL)
print("⏰ Limite: 1000 requêtes/jour")
bot.run(DISCORD_TOKEN)
