# LoL Spy - Discord Bot

Este es un bot de Discord hecho en Python que te notifica cuando tus amigos están en una partida de League of Legends.

## Configuración

Antes de ejecutar el bot, asegúrate de configurar algunas variables en el archivo `bot.py`. Aquí está lo que necesitas hacer:

1. **Token de Discord**:
    - Obtén tu token de Discord siguiendo las instrucciones en la documentación oficial de Discord.
    - Reemplaza `'DISCORD_TOKEN'` en el archivo `bot.py` con tu token de Discord.

2. **Clave de la API de Riot Games**:
    - Obtén tu clave de la API de Riot Games registrándote en el [Portal de Desarrolladores de Riot Games](https://developer.riotgames.com/).
    - Reemplaza `'RIOT_API_KEY'` en el archivo `bot.py` con tu clave de la API de Riot Games.

3. **ID del canal de Discord**:
    - Obtén el ID del canal de Discord en el que deseas que el bot envíe las notificaciones.
    - Reemplaza `CHANNEL_ID` en el archivo `bot.py` con el ID de tu canal de Discord.

4. **Lista de amigos**:
    - En la lista `amigos` en el archivo `bot.py`, agrega los nombres de invocador de tus amigos en League of Legends.

## Ejecución del Bot

Una vez que hayas configurado las variables mencionadas anteriormente, puedes ejecutar el bot ejecutando el siguiente comando en tu terminal:

```bash
py bot.py
```

El bot se conectará a Discord y comenzará a verificar el estado de juego de tus amigos.