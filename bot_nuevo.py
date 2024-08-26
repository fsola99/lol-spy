import discord
from discord.ext import tasks
import aiohttp
import asyncio
import json

# Definir intents
intents = discord.Intents.default()
intents.presences = True
intents.guilds = True
intents.members = True

# Lee la configuración desde el archivo config.json
with open('config.json') as f:
    config = json.load(f)

# Variables globales
DISCORD_TOKEN = config['DISCORD_TOKEN']
RIOT_API_KEY = config['RIOT_API_KEY']
CHANNEL_ID = int(config['CHANNEL_ID'])
REQUESTS_PER_MINUTE = int(config['REQUESTS_PER_MINUTE'])
FRIENDS_LIST = config['FRIENDS_LIST']

# Diccionario para mantener un registro de los amigos y sus puuids
friends_puuids = {}

# Diccionario para mantener un registro de los amigos y sus partidas notificadas
partidas_notificadas = {}

# Variable para verificar si se ha enviado un mensaje de falta de partidas
missing_games_notified = False

# Semáforo para controlar el acceso a la API y respetar el límite de velocidad
api_semaphore = asyncio.Semaphore(REQUESTS_PER_MINUTE)

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('Bot conectado como {0.user}'.format(client))
    # Buscar los puuids de los amigos cuando se inicia el bot
    await fetch_friends_puuids()
    # Iniciar el loop que comprueba el estado de juego de los amigos
    check_friends_game.start()

async def fetch_friends_puuids():
    async with aiohttp.ClientSession() as session:
        for amigo in FRIENDS_LIST:
            game_name = amigo['gameName']
            tag_line = amigo['tagLine']
            puuid = await get_puuid(session, game_name, tag_line)
            if puuid:
                friends_puuids[game_name] = puuid
                print(f'PUUID para {game_name}: {puuid}')
            else:
                print(f'No se pudo obtener el PUUID para {game_name}')

async def get_puuid(session, game_name, tag_line):
    url = f'https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={RIOT_API_KEY}'
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data.get('puuid')
        else:
            print(f'Error al obtener el PUUID para {game_name}: {response.status}')
            return None
        
async def get_current_game(session, puuid):
    url = f'https://la2.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}?api_key={RIOT_API_KEY}'
    async with session.get(url) as response:
        if response.status == 200:
            return await response.json()
        elif response.status == 404: # Si devuelve 404, el amigo no está en partida
            return None
        else:
            print(f'Error al obtener la partida actual para el invocador {puuid}: {response.status}')
            return None

def notificar_partida(amigo, game_data):
    if amigo not in partidas_notificadas:
        partidas_notificadas[amigo] = game_data['gameId']
        return True
    elif partidas_notificadas[amigo] != game_data['gameId']:
        partidas_notificadas[amigo] = game_data['gameId']
        return True
    else:
        return False

async def get_champion_name(champion_id):
    game_version = await get_game_version()
    if game_version:
        url = f'http://ddragon.leagueoflegends.com/cdn/{game_version}/data/en_US/champion.json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    champions_data = data.get('data')
                    for champion in champions_data.values():
                        if champion['key'] == str(champion_id):
                            return champion['name']
                print(f"Error: Campeón con ID {champion_id} no encontrado.")
    else:
        print("Error: No se pudo obtener la versión del juego para buscar el campeón.")
    return None

async def get_game_version():
    url = 'https://ddragon.leagueoflegends.com/api/versions.json'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                versions = await response.json()
                if versions:
                    return versions[0]  # La versión más reciente es la primera en la lista
                else:
                    print("Error: No se encontraron versiones disponibles.")
            else:
                print(f"Error al obtener la versión del juego: {response.status}")
    return None

async def notify_missing_games():
    # Enviar mensaje de falta de partidas al canal de Discord
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("Ninguno de tus amigos está actualmente en partida.")

async def notify_game_status(amigo, game_data):
    global missing_games_notified

    # Buscar el participante correspondiente al amigo en los datos de la partida
    puuid = friends_puuids.get(amigo['gameName'])
    if puuid:
        participant = next((p for p in game_data['participants'] if p['puuid'] == puuid), None)
        if participant:
            # Obtener el ID del campeón que está jugando el amigo
            champion_id = participant['championId']
            champion_name = await get_champion_name(champion_id)
            if champion_name:
                game_mode = game_data['gameMode']
                # Formatear el mensaje
                message = f"**{amigo['gameName']}** está jugando: **{champion_name}** en modo de juego **{game_mode}**"
                
                # Enviar el mensaje al canal de Discord
                channel = client.get_channel(CHANNEL_ID)
                embed = discord.Embed(
                    title="¡Un amigo está en partida!",
                    description=message,
                    color=discord.Color.green() # Cambia el color del mensaje si lo deseas
                )
                await channel.send(embed=embed)
                missing_games_notified = True
            else:
                print(f"Error: Campeón con ID {champion_id} no encontrado.")
        else:
            print(f"Error: Participante {amigo['gameName']} no encontrado en los datos de la partida.")
    else:
        print(f"Error: PUUID para {amigo['gameName']} no encontrado en el diccionario de PUUIDs.")

@tasks.loop(seconds=60)
async def check_friends_game():
    global missing_games_notified
    
    async with aiohttp.ClientSession() as session:
        found_game = False
        for amigo in FRIENDS_LIST:
            puuid = friends_puuids.get(amigo['gameName'])
            if puuid:
                async with api_semaphore:
                    game_data = await get_current_game(session, puuid)
                if game_data:
                    if notificar_partida(amigo['gameName'], game_data):
                        await notify_game_status(amigo, game_data)
                        found_game = True
        if not found_game and not missing_games_notified:
            await notify_missing_games()
            missing_games_notified = True

client.run(DISCORD_TOKEN)
