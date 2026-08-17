import os
import discord
from discord import app_commands
from openai import OpenAI

# Récupération automatique depuis les variables d'environnement du serveur
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Configuration du client OpenAI pour Groq
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Configuration de Intents pour le bot
intents = discord.Intents.default()
intents.message_content = True  # Nécessaire pour lire le contenu des messages dans le jeu

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes slash synchronisées.")

bot = MyBot()

# État du jeu par salon (sauvegarde le salon actif, le dernier mot, le dernier joueur et l'historique)
game_sessions = {}

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user} (ID: {bot.user.id})")

# Commande /ping pour tester le bot et l'IA
@bot.tree.command(name="ping", description="Vérifie si le bot et l'IA fonctionnent.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    ai_status = "OK"
    try:
        # Test rapide de l'IA avec Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Modèle rapide et gratuit sur Groq
            messages=[{"role": "user", "content": "Réponds juste 'Pong'"}],
            max_tokens=5
        )
        ai_reply = response.choices[0].message.content.strip()
    except Exception as e:
        ai_status = f"Erreur : {e}"

    await interaction.followup.send(f"Pong 🏓 !\nStatut de l'IA : **{ai_status}**")

# Commande /jeu-grandeur
@bot.tree.command(name="jeu-grandeur", description="Active ou désactive le jeu de la grandeur dans un salon.")
@app_commands.describe(
    statut="Activer ou désactiver le jeu",
    salon="Le salon où se déroulera le jeu"
)
@app_commands.choices(statut=[
    app_commands.Choice(name="activé", value="active"),
    app_commands.Choice(name="désactivé", value="desactive")
])
async def jeu_grandeur(interaction: discord.Interaction, statut: app_commands.Choice[str], salon: discord.TextChannel):
    if statut.value == "active":
        # Initialisation d'une nouvelle partie
        premier_mot = "univers" # Mot de départ par défaut
        game_sessions[salon.id] = {
            "active": True,
            "dernier_mot": premier_mot,
            "dernier_joueur": None,
            "historique": [premier_mot]
        }
        await interaction.response.send_message(f"Le jeu de la grandeur est **activé** dans {salon.mention} !\n🚀 Premier mot donné par le bot : **{premier_mot}**")
    else:
        if salon.id in game_sessions:
            del game_sessions[salon.id]
        await interaction.response.send_message(f"Le jeu de la grandeur est **désactivé** dans {salon.mention}.")

# Écouteur de messages pour le déroulement du jeu
@bot.event
async def on_message(message: discord.Message):
    # Ignorer les messages des bots ou les messages hors salons de jeu
    if message.author.bot or message.channel.id not in game_sessions:
        return

    session = game_sessions[message.channel.id]
    if not session["active"]:
        return

    # Règle : Interdit de jouer 2 fois d'affilée
    if message.author.id == session["dernier_joueur"]:
        await message.add_reaction("❌")
        await message.channel.send(f"{message.author.mention} Tu ne peux pas jouer deux fois de suite !")
        return

    nouveau_mot = message.content.strip()
    dernier_mot = session["dernier_mot"]

    # Demande à l'IA de valider si le nouveau mot est "supérieur" (concept, taille, puissance, échelle, etc.)
    prompt = (
        f"Tu es l'arbitre d'un jeu de logique et d'échelle. "
        f"Le mot précédent était '{dernier_mot}' et le nouveau mot proposé est '{nouveau_mot}'. "
        f"Est-ce que '{nouveau_mot}' est logiquement supérieur, plus grand, plus fort, ou d'une échelle supérieure à '{dernier_mot}' ? "
        f"Réponds uniquement par 'OUI' ou 'NON'."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10
        )
        reponse_ia = response.choices[0].message.content.strip().upper()
    except Exception as e:
        print(f"Erreur IA : {e}")
        return

    if "OUI" in reponse_ia:
        # Validation
        session["dernier_mot"] = nouveau_mot
        session["dernier_joueur"] = message.author.id
        session["historique"].append(nouveau_mot)
        await message.add_reaction("✅")
    else:
        # Erreur / Partie perdue
        historique_str = " -> ".join(session["historique"])
        await message.add_reaction("❌")
        await message.channel.send(
            f"❌ **Perdu !** '{nouveau_mot}' n'est pas considéré comme supérieur à '{dernier_mot}'.\n"
            f"📜 **Historique de la partie :** {historique_str}"
        )
        
        # Relance avec un nouveau premier mot
        nouveau_premier_mot = "atome"
        session["dernier_mot"] = nouveau_premier_mot
        session["dernier_joueur"] = None
        session["historique"] = [nouveau_premier_mot]
        await message.channel.send(f"🔄 Une nouvelle partie recommence ! Le nouveau mot de départ est : **{nouveau_premier_mot}**")

# Lancement du bot avec le token de la variable d'environnement
bot.run(DISCORD_TOKEN)
