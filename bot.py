import discord
from discord.ext import tasks
import aiohttp
import asyncio
import urllib.parse


# Definir intents
intents = discord.Intents.default()
intents.presences = True
intents.guilds = True
intents.members = True

#  Variables globales
DISCORD_TOKEN = 'your_discord_token'
RIOT_API_KEY = 'your_riot_api_key'
CHANNEL_ID = 1234567890  # ID del canal donde enviar notificaciones

# Lista de amigos
amigos = ['pepe', 'pipo', 'pepa']

# Diccionario para mantener un registro de los amigos y sus partidas notificadas
partidas_notificadas = {}

# Variable para verificar si se ha enviado un mensaje de falta de partidas
missing_games_notified = False

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('Bot conectado como {0.user}'.format(client))
    # Iniciar el loop que comprueba el estado de juego de los amigos
    check_friends_game.start()

@tasks.loop(seconds=60)
async def check_friends_game():
    global missing_games_notified
    
    async with aiohttp.ClientSession() as session:
        found_game = False
        for amigo in amigos:
            summoner_id = await get_summoner_id(session, amigo)
            if summoner_id:
                game_data = await get_current_game(session, summoner_id)
                if game_data:
                    if notificar_partida(amigo, game_data):
                        await notify_game_status(amigo, game_data)
                        found_game = True
        if not found_game and not missing_games_notified:
            await notify_missing_games()
            missing_games_notified = True

def notificar_partida(amigo, game_data):
    if amigo not in partidas_notificadas:
        partidas_notificadas[amigo] = game_data['gameId']
        return True
    elif partidas_notificadas[amigo] != game_data['gameId']:
        partidas_notificadas[amigo] = game_data['gameId']
        return True
    else:
        return False

async def get_summoner_id(session, summoner_name):
    summoner_name_encoded = urllib.parse.quote(summoner_name)
    url = f'https://la2.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name_encoded}'
    headers = {'X-Riot-Token': RIOT_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            return data.get('id')
        else:
            print(f'Error al obtener el ID de invocador para {summoner_name}: {response.status}')
            return None

async def get_current_game(session, summoner_id):
    url = f'https://la2.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/{summoner_id}'
    headers = {'X-Riot-Token': RIOT_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        elif response.status == 404: # Si devuelve 404, el amigo no está en partida
            return None
        else:
            print(f'Error al obtener la partida actual para el invocador {summoner_id}: {response.status}')
            return None

async def notify_game_status(amigo, game_data):
    # Convertir el nombre del amigo a minúsculas
    amigo_lower = amigo.lower()
    
    # Buscar el participante correspondiente al amigo en los datos de la partida
    participant = next((p for p in game_data['participants'] if p['summonerName'].lower() == amigo_lower), None)
    if participant:
        # Obtener el ID del campeón que está jugando el amigo
        champion_id = participant['championId']
        champion_name = await get_champion_name(champion_id)
        if champion_name:
            game_mode = game_data['gameMode']
            # Formatear el mensaje
            message = f"**{amigo}** está jugando: **{champion_name}** en modo de juego **{game_mode}**"
            
            # Enviar el mensaje al canal de Discord
            channel = client.get_channel(CHANNEL_ID)
            embed = discord.Embed(
                title="¡Un amigo está en partida!",
                description=message,
                color=discord.Color.green() # Cambia el color del mensaje si lo deseas
            )
            await channel.send(embed=embed)
        else:
            print(f"Error: Campeón con ID {champion_id} no encontrado.")
    else:
        print(f"Error: Participante {amigo} no encontrado en los datos de la partida.")

async def get_champion_name(champion_id):
    url = f'http://ddragon.leagueoflegends.com/cdn/11.21.1/data/en_US/champion.json'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                champions_data = data.get('data')
                for champion in champions_data.values():
                    if champion['key'] == str(champion_id):
                        return champion['name']
            return None

async def notify_missing_games():
    # Enviar mensaje de falta de partidas al canal de Discord
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("Ninguno de tus amigos está actualmente en partida.")

client.run(DISCORD_TOKEN)