from logging.handlers import RotatingFileHandler
import re
import sys

import sqlalchemy as sa
from utils import schema
import bs4
import requests
import pandas as pd
import logging
import asyncio

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
handler = RotatingFileHandler("logs/world_scraper.log", maxBytes=100000, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


def getworlds():
    worldlist = []
    try:
        worlds = requests.get("http://oldschool.runescape.com/slu")
        soup = bs4.BeautifulSoup(worlds.text, "html.parser")
        # get the table "server-list" as a pandas dataframe
        table = pd.read_html(str(soup.find("table", class_="server-list")))[0]
        # name the columns   World	  Players	  Location	  members	  Activity
        table.columns = ["world", "players_str", "location", "type", "activity"]
        LOGGER.debug(f"Table: {table}")
        # get the world ids, this is the same length as the table
        server_list = soup.find_all("a", "server-list__world-link")
        table["world_id"] = [
            int(re.search(r"\d+", server["id"]).group()) for server in server_list
        ]
        table["world_url"] = table["world"].apply(
            lambda x: f"http://{str(x).replace(' ', '').lower()}.runescape.com/"
        )
        table["members"] = table["type"].apply(
            lambda x: True if x == "Members" else False
        )
        # table["players"] = table["players_str"].apply(
        #     lambda x: int(re.search(r"\d+", x).group())
        # )
        for i, row in table.iterrows():
            player_count = re.search(r"\d+", row["players_str"])
            if player_count:
                table.at[i, "players"] = int(player_count.group())
            else:
                table.at[i, "players"] = 0
        # convert the table to a list of dictionaries ready to be inserted into the database
        worldlist = table.to_dict(orient="records")
    except Exception as e:
        LOGGER.error(f"Error getting world list: {e}")
        # log the traceback
        LOGGER.exception(e)
        return worldlist
    return worldlist


async def ping_world(world_url, world_id, players, semaphore):
    async with semaphore:
        LOGGER.info(f"Pinging {world_url}...")
        try:
            ping = requests.get(world_url).elapsed.total_seconds()
            # use aio to sleep this thread for 1 second to avoid rate limiting
            # the semaphore is released after the sleep
            await asyncio.sleep(1)
        except Exception as e:
            LOGGER.error(f"Error pinging {world_url}: {e}")
            ping = 9999.0
        ping_data = schema.PingData(
            world_id=world_id,
            timestamp=pd.Timestamp.now(),
            ping=ping,
            players=int(players),
        )
        LOGGER.info(f"Pinged {world_url} with {ping} seconds and {players} players")
        return ping_data


async def insert_worlds(worlds):
    worlds_df = pd.DataFrame(worlds)
    LOGGER.info(f"Worlds:\n{worlds}")
    # create the database
    engine = sa.create_engine("sqlite:///data/world_data.db")
    schema.Base.metadata.create_all(engine)
    # insert the data into the database
    with schema.get_session(engine=engine) as session:
        worlds_to_insert = []
        for world in worlds:
            if not isinstance(world, dict):
                LOGGER.error(f"Invalid world data: {world}")
                continue
            # check if the world is already in the database, if not insert it
            if (
                not session.query(schema.OSRSWorlds)
                .filter_by(world_id=world["world_id"])
                .first()
            ):
                _world = {
                    k: v
                    for k, v in world.items()
                    if k in schema.OSRSWorlds.__table__.columns.keys()
                }
                worlds_to_insert.append(schema.OSRSWorlds(**_world))
        session.add_all(worlds_to_insert)
        LOGGER.info(f"Data inserted for {len(worlds_to_insert)} worlds")
        # ping all members worlds in Germany or United Kingdom, also store their player count
        semaphore = asyncio.Semaphore(5)  # limit the number of concurrent requests
        ping_tasks = []
        for world in session.query(schema.OSRSWorlds).filter(
            sa.or_(
                schema.OSRSWorlds.location == "Germany",
                schema.OSRSWorlds.location == "United Kingdom",
            ),
            schema.OSRSWorlds.members == True,
            schema.OSRSWorlds.activity == "-",
        ):
            ping_task = ping_world(
                world.world_url,
                world.world_id,
                worlds_df.loc[
                    worlds_df["world_id"] == world.world_id, "players"
                ].values[0],
                semaphore,
            )
            ping_tasks.append(ping_task)
        ping_results = await asyncio.gather(*ping_tasks)
        session.add_all(ping_results)
        session.commit()
    LOGGER.info(
        f"Fetched {len(worlds)} worlds and pinged {len(worlds_to_insert)} members worlds in Germany or United Kingdom"
    )


async def main():
    try:
        worlds = getworlds()
        await insert_worlds(worlds)
    except Exception as e:
        LOGGER.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
