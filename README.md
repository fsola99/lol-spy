# LoL Spy - Discord Bot

Lol Spy es un bot de Discord hecho en Python que te notifica cuando tus amigos están en una partida de League of Legends.

## Configuración

Antes de ejecutar el bot, asegúrate de seguir estos pasos:

1. **Crear el archivo `config.json`**:
    - Crea un nuevo archivo llamado `config.json` en la misma ubicación que el archivo `bot.py`.
    - Dentro de este archivo, copia y pega el siguiente contenido:

```json
{
    "DISCORD_TOKEN": "tu_token_de_discord",
    "RIOT_API_KEY": "tu_api_key_de_riot",
    "CHANNEL_ID": "tu_id_de_canal",
    "REQUESTS_PER_MINUTE": 20,
    "FRIENDS_LIST": ["amigo1", "amigo2", "amigo3"]
}
```

2. **Token de Discord**:
    - Obtén tu token de Discord siguiendo las instrucciones en la documentación oficial de Discord.
    - Coloca tu token de Discord en el campo `"DISCORD_TOKEN"` dentro del archivo `config.json`.

3. **Clave de la API de Riot Games**:
    - Obtén tu clave de la API de Riot Games registrándote en el [Portal de Desarrolladores de Riot Games](https://developer.riotgames.com/).
    - Coloca tu clave de la API de Riot Games en el campo `"RIOT_API_KEY"` dentro del archivo `config.json`.

4. **ID del canal de Discord**:
    - Obtén el ID del canal de Discord en el que deseas que el bot envíe las notificaciones.
    - Coloca el ID de tu canal de Discord en el campo `"CHANNEL_ID"` dentro del archivo `config.json`.

5. **Lista de amigos**:
    - En el campo `"FRIENDS_LIST"` dentro del archivo `config.json`, agrega los nombres de invocador de tus amigos en League of Legends.

## Ejecución del bot

Después de configurar el archivo `config.json`, puedes ejecutar el bot ejecutando el siguiente comando en tu terminal:

```bash
py bot.py
```

El bot se conectará a Discord y comenzará a verificar el estado de juego de tus amigos.