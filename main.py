import os
import discord
from discord import app_commands
from openai import OpenAI
import random

# Récupération automatique depuis les variables d'environnement du serveur
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

intents = discord.Intents.default()
intents.message_content = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes slash synchronisées.")

bot = MyBot()

# Stockage des sessions de jeu
game_sessions = {}

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user} (ID: {bot.user.id})")

@bot.tree.command(name="ping", description="Vérifie si le bot et l'IA fonctionnent.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    
    ai_status = "OK"
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",  # 🔧 Changé pour un modèle plus stable
            messages=[{"role": "user", "content": "Réponds juste 'Pong'"}],
            max_tokens=10
        )
        print(f"[PING] Réponse brute: '{response.choices[0].message.content}'")
    except Exception as e:
        ai_status = f"Erreur : {e}"

    await interaction.followup.send(f"Pong 🏓 !\nStatut de l'IA : **{ai_status}**")

async def generer_premier_mot():
    """Demande à l'IA de générer un mot de départ aléatoire"""
    prompt = "Propose UN SEUL mot représentant quelque chose de petit (atome, cellule, grain, etc). Réponds uniquement avec le mot."
    
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",  # 🔧 Modèle plus stable
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.7
        )
        mot = response.choices[0].message.content.strip().lower()
        print(f"[IA-GENERER] Réponse brute: '{response.choices[0].message.content}' | Mot traité: '{mot}'")
        
        # Nettoyage si l'IA ajoute du texte en plus
        if len(mot) > 20:  # Si c'est trop long, prendre le premier mot
            mot = mot.split()[0]
        
        if mot:
            return mot
        else:
            print(f"[ERREUR] Réponse vide reçue, utilisation du fallback")
            return "atome"
    except Exception as e:
        print(f"[ERREUR] Impossible de générer un mot : {e}")
        return "atome"

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
        # L'IA génère le premier mot
        premier_mot = await generer_premier_mot()
        print(f"[COMMANDE] Jeu activé avec mot de départ: '{premier_mot}'")
        
        game_sessions[salon.id] = {
            "active": True,
            "dernier_mot": premier_mot,
            "dernier_joueur": None,
            "historique": [premier_mot]
        }
        await interaction.response.send_message(f"Le jeu de la grandeur est **activé** dans {salon.mention} !\n🚀 Premier mot donné par l'IA : **{premier_mot}**")
    else:
        if salon.id in game_sessions:
            del game_sessions[salon.id]
        await interaction.response.send_message(f"Le jeu de la grandeur est **désactivé** dans {salon.mention}.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.channel.id not in game_sessions:
        return

    session = game_sessions[message.channel.id]
    if not session["active"]:
        return

    if message.author.id == session["dernier_joueur"]:
        await message.add_reaction("❌")
        await message.channel.send(f"{message.author.mention} Tu ne peux pas jouer deux fois de suite !")
        return

    nouveau_mot = message.content.strip().lower()
    dernier_mot = session["dernier_mot"]
    
    print(f"\n[GAME-START] Nouveau message du joueur: '{nouveau_mot}'")
    print(f"[GAME-STATE] Mot précédent en mémoire: '{dernier_mot}'")

    # Prompt TRÈS simple et explicite
    prompt = (
        f"Question simple : '{nouveau_mot}' est-il plus GRAND ou plus PUISSANT que '{dernier_mot}' ?\n"
        f"Réponds avec UN SEUL MOT : OUI ou NON\n"
        f"Exemple: Si '{dernier_mot}' = 'atome' et '{nouveau_mot}' = 'molécule', réponds: OUI"
    )

    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",  # 🔧 Modèle plus stable
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.1
        )
        reponse_brute = response.choices[0].message.content.strip().upper()
        print(f"[IA-REPONSE] Réponse brute de l'IA: '{reponse_brute}'")
        
        # Nettoyage de la réponse
        reponse_ia = reponse_brute.replace(".", "").replace(",", "").replace("!", "").strip()
        print(f"[IA-NETTOYEE] Réponse nettoyée: '{reponse_ia}'")
        
    except Exception as e:
        print(f"[ERREUR IA] {e}")
        await message.channel.send(f"⚠️ Erreur de l'IA : {e}")
        return

    # Vérification stricte
    if "OUI" in reponse_ia:
        print(f"[DECISION] ACCEPTÉ - '{nouveau_mot}' est valide !")
        session["dernier_mot"] = nouveau_mot
        session["dernier_joueur"] = message.author.id
        session["historique"].append(nouveau_mot)
        await message.add_reaction("✅")
    else:
        print(f"[DECISION] REJETÉ - '{nouveau_mot}' n'est pas valide. Réponse: {reponse_ia}")
        
        # Partie perdue
        historique_str = " -> ".join(session["historique"])
        await message.add_reaction("❌")
        await message.channel.send(
            f"❌ **Perdu !** '{nouveau_mot}' n'est pas supérieur à '{dernier_mot}'.\n"
            f"📜 **Historique :** {historique_str}\n"
            f"💬 **Réponse de l'IA :** {reponse_ia}"
        )
        
        # L'IA génère un nouveau mot de départ
        nouveau_premier_mot = await generer_premier_mot()
        print(f"[NOUVELLE-PARTIE] Nouveau mot: '{nouveau_premier_mot}'")
        
        session["dernier_mot"] = nouveau_premier_mot
        session["dernier_joueur"] = None
        session["historique"] = [nouveau_premier_mot]
        await message.channel.send(f"🔄 Nouvelle partie ! L'IA a choisi : **{nouveau_premier_mot}**")

bot.run(DISCORD_TOKEN)
