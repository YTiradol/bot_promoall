import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration
API_URL = os.getenv('API_URL', 'https://monde8.empireimmo.com/api/buildings.json?key=eiK8_abffd893ce198bc434ef809fa8a1ac20')
DATA_FILE = os.getenv('DATA_FILE', 'buildings.json')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN non trouvé dans .env. Créez un fichier .env avec votre token!")

# Initialiser le bot avec intents
intents = discord.Intents.default()
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="/", intents=intents)

# ============= FONCTIONS UTILITAIRES =============

async def fetch_api_data():
    """Récupère les données de l'API Empire Immo"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Erreur API: Status {response.status}")
                    return None
    except asyncio.TimeoutError:
        print("❌ Timeout lors de la récupération API")
        return None
    except Exception as e:
        print(f"❌ Erreur lors de la récupération API: {e}")
        return None

def save_data(data):
    """Sauvegarde les données dans un fichier JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False

def load_data():
    """Charge les données depuis le fichier JSON"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"❌ Erreur lors du chargement des données: {e}")
        return None

def format_price(price):
    """Formate un prix pour l'affichage lisible"""
    price = float(price)
    if price >= 1_000_000_000_000_000_000:  # 1 Exaillion
        return f"{price / 1_000_000_000_000_000_000:.2f}Exa"
    elif price >= 1_000_000_000_000_000:  # 1 Pétaillion
        return f"{price / 1_000_000_000_000_000:.2f}Pet"
    elif price >= 1_000_000_000_000:  # 1 Trilliard
        return f"{price / 1_000_000_000_000:.2f}T"
    elif price >= 1_000_000_000:  # 1 Milliard
        return f"{price / 1_000_000_000:.2f}Md"
    elif price >= 1_000_000:  # 1 Million
        return f"{price / 1_000_000:.2f}M"
    elif price >= 1_000:  # 1 Mille
        return f"{price / 1_000:.2f}k"
    else:
        return str(int(price))

def format_price_exact(price):
    """Retourne le prix exact formaté avec séparateurs"""
    price = int(float(price))
    return f"{price:,}".replace(",", " ")

# ============= ÉVÉNEMENTS =============

@bot.event
async def on_ready():
    """Événement appelé quand le bot est prêt"""
    try:
        synced = await bot.tree.sync()
        print(f"✅ Commandes synchronisées: {len(synced)}")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation: {e}")
    print(f"🤖 {bot.user} est connecté!")

# ============= COMMANDES SLASH =============

@bot.tree.command(
    name="maj_api",
    description="📥 Met à jour le fichier buildings.json avec les données de l'API"
)
async def maj_api(interaction: discord.Interaction):
    """Met à jour les données via l'API"""
    await interaction.response.defer()
    
    # Récupérer les données
    data = await fetch_api_data()
    
    if data is None:
        embed = discord.Embed(
            title="❌ Erreur de connexion",
            description="Impossible de récupérer les données de l'API.\nVérifiez votre connexion internet et l'URL de l'API.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Empire Immo Bot")
        await interaction.followup.send(embed=embed)
        return
    
    # Sauvegarder les données
    if save_data(data):
        nb_perso = len(data.get('batiments_perso', []))
        nb_entreprise = len(data.get('batiments_entreprise', []))
        nb_terrain = len(data.get('batiments_terrain', []))
        
        embed = discord.Embed(
            title="✅ Mise à jour réussie",
            description="Les données ont été synchronisées avec l'API",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 Statistiques",
            value=f"👤 Personnels: {nb_perso}\n🏢 Entreprise: {nb_entreprise}\n🏞️ Terrains: {nb_terrain}",
            inline=False
        )
        embed.add_field(
            name="🕐 Timestamp",
            value=data.get('mise_a_jour', 'N/A'),
            inline=False
        )
        embed.set_footer(text=f"Fichier: {DATA_FILE}")
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Erreur de sauvegarde",
            description="Les données n'ont pas pu être sauvegardées.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(
    name="prix_revente",
    description="💰 Affiche les Technopôle et Mégapôle avec prix augmenté"
)
@app_commands.describe(
    pourcentage="Pourcentage d'augmentation (ex: 10 pour +10%)"
)
async def prix_revente(interaction: discord.Interaction, pourcentage: float):
    """Affiche les prix avec augmentation"""
    
    # Valider le pourcentage
    if pourcentage < 0:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Le pourcentage doit être positif!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    await interaction.response.defer()
    
    # Charger les données
    data = load_data()
    
    if data is None:
        embed = discord.Embed(
            title="❌ Pas de données",
            description="Aucune donnée trouvée.\n\nUtilisez `/maj_api` d'abord pour télécharger les données.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        return
    
    # Récupérer les bâtiments entreprise
    batiments_entreprise = data.get('batiments_entreprise', [])
    
    # Filtrer Technopôle et Mégapôle
    tech_mega = [
        b for b in batiments_entreprise 
        if 'Technopôle' in b.get('nom', '') or 'Mégapôle' in b.get('nom', '')
    ]
    
    # Trier par prix décroissant
    tech_mega.sort(key=lambda x: float(x.get('valeur', 0)), reverse=True)
    
    if not tech_mega:
        embed = discord.Embed(
            title="ℹ️ Aucun bâtiment trouvé",
            description="Aucun Technopôle ou Mégapôle trouvé dans les données.",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed)
        return
    
    # Créer les embeds (limite de 2000 caractères par embed Discord)
    embeds = []
    current_embed = discord.Embed(
        title=f"💰 Prix Revente - Augmentation de {pourcentage:g}%",
        description=f"Affichage de {len(tech_mega)} bâtiment(s)",
        color=discord.Color.blue()
    )
    
    char_count = 0
    
    for batiment in tech_mega:
        nom = batiment.get('nom', 'Inconnu')
        prix_original = float(batiment.get('valeur', 0))
        augmentation = prix_original * (pourcentage / 100)
        prix_revente = prix_original + augmentation
        
        # Créer le contenu du champ
        field_value = (
            f"**Original:** {format_price(prix_original)}\n"
            f"**Augmentation:** {format_price(augmentation)}\n"
            f"**Revente:** **{format_price(prix_revente)}**\n"
            f"```\nPrix exact: {format_price_exact(prix_revente)}\n```"
        )
        
        # Vérifier la longueur pour ne pas dépasser les limites Discord
        if char_count + len(field_value) > 1800:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title=f"💰 Prix Revente - Suite",
                color=discord.Color.blue()
            )
            char_count = 0
        
        current_embed.add_field(name=f"🏗️ {nom}", value=field_value, inline=False)
        char_count += len(field_value)
    
    if current_embed.fields:
        embeds.append(current_embed)
    
    # Ajouter les footers
    if embeds:
        for i, embed in enumerate(embeds):
            if i == len(embeds) - 1:  # Dernier embed
                embed.set_footer(
                    text=f"Mise à jour: {data.get('mise_a_jour', 'N/A')} | {data.get('nom', '')}"
                )
            else:
                embed.set_footer(text=f"Page {i + 1}")
    
    # Envoyer les embeds
    for embed in embeds:
        await interaction.followup.send(embed=embed)
    
    # Créer un message avec les prix en texte brut (facile à copier)
    if tech_mega:
        prix_texte = f"PRIX REVENTE - Augmentation {pourcentage:g}%\n"
        prix_texte += f"{'=' * 60}\n\n"
        
        for batiment in tech_mega:
            nom = batiment.get('nom', 'Inconnu')
            prix_original = float(batiment.get('valeur', 0))
            prix_revente = prix_original * (1 + pourcentage / 100)
            
            prix_texte += f"{nom}\n"
            prix_texte += f"  Original: {format_price(prix_original)} ({format_price_exact(prix_original)})\n"
            prix_texte += f"  Prix Revente: {format_price(prix_revente)} ({format_price_exact(prix_revente)})\n\n"
        
        # Envoyer le texte par chunks si trop long
        if len(prix_texte) < 1990:
            await interaction.followup.send(f"```\n{prix_texte}\n```")
        else:
            chunks = [prix_texte[i:i+1900] for i in range(0, len(prix_texte), 1900)]
            for chunk in chunks:
                await interaction.followup.send(f"```\n{chunk}\n```")

@bot.tree.command(
    name="stats",
    description="📊 Affiche les statistiques des bâtiments"
)
async def stats(interaction: discord.Interaction):
    """Affiche les statistiques"""
    await interaction.response.defer()
    
    data = load_data()
    
    if data is None:
        embed = discord.Embed(
            title="❌ Pas de données",
            description="Aucune donnée trouvée.\n\nUtilisez `/maj_api` d'abord.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        return
    
    nb_perso = len(data.get('batiments_perso', []))
    nb_entreprise = len(data.get('batiments_entreprise', []))
    nb_terrain = len(data.get('batiments_terrain', []))
    
    # Compter les Technopôle et Mégapôle
    batiments_entreprise = data.get('batiments_entreprise', [])
    tech_mega = [b for b in batiments_entreprise if 'Technopôle' in b.get('nom', '') or 'Mégapôle' in b.get('nom', '')]
    
    embed = discord.Embed(
        title="📊 Statistiques des bâtiments",
        color=discord.Color.gold()
    )
    embed.add_field(name="👤 Bâtiments Personnels", value=str(nb_perso), inline=True)
    embed.add_field(name="🏢 Bâtiments Entreprise", value=str(nb_entreprise), inline=True)
    embed.add_field(name="🏞️ Terrains", value=str(nb_terrain), inline=True)
    embed.add_field(name="🏗️ Technopôle/Mégapôle", value=str(len(tech_mega)), inline=True)
    embed.set_footer(text=f"Mise à jour: {data.get('mise_a_jour', 'N/A')} | {data.get('nom', '')}")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(
    name="aide",
    description="❓ Affiche l'aide sur les commandes"
)
async def aide(interaction: discord.Interaction):
    """Affiche l'aide"""
    embed = discord.Embed(
        title="❓ Aide du Bot Empire Immo",
        description="Voici les commandes disponibles:",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="/maj_api",
        value="Télécharge et met à jour les données des bâtiments depuis l'API",
        inline=False
    )
    
    embed.add_field(
        name="/prix_revente <pourcentage>",
        value="Affiche tous les Technopôle et Mégapôle avec prix augmenté\n*Exemple: `/prix_revente 15` pour +15%*",
        inline=False
    )
    
    embed.add_field(
        name="/stats",
        value="Affiche les statistiques des bâtiments",
        inline=False
    )
    
    embed.add_field(
        name="/aide",
        value="Affiche cette aide",
        inline=False
    )
    
    embed.set_footer(text="Bot Empire Immo | Monde 8")
    
    await interaction.response.send_message(embed=embed)

# ============= DÉMARRAGE =============

import asyncio

async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    print("🚀 Démarrage du bot Empire Immo...")
    print(f"📁 Fichier de données: {DATA_FILE}")
    print(f"🔗 API URL: {API_URL[:50]}...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Bot arrêté par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur critique: {e}")
