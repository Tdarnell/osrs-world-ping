from logging.handlers import RotatingFileHandler
import re
import sys
import time

import sqlalchemy as sa
from utils import schema
from pathlib import Path
import bs4
import requests
import pandas as pd
import logging

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
        LOGGER.debug(f"Table: {table}")
        # name the columns   World	  Players	  Location	  members	  Activity
        table.columns = ["world", "players_str", "location", "type", "activity"]
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
        table["players"] = table["players_str"].apply(
            lambda x: int(re.search(r"\d+", x).group())
        )
        # convert the table to a list of dictionaries ready to be inserted into the database
        worldlist = table.to_dict(orient="records")
    except Exception as e:
        LOGGER.error(f"Error getting world list: {e}")
        return worldlist
    return worldlist


if __name__ == "__main__":
    worlds = getworlds()
    worlds_df = pd.DataFrame(worlds)
    LOGGER.info(f"Worlds:\n{worlds}")
    # create the database
    engine = sa.create_engine("sqlite:///data/world_data.db")
    schema.Base.metadata.create_all(engine)
    # insert the data into the database
    with schema.get_session(engine=engine) as session:
        worlds_to_insert = []
        for world in worlds:
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
        for world in session.query(schema.OSRSWorlds).filter(
            sa.or_(
                schema.OSRSWorlds.location == "Germany",
                schema.OSRSWorlds.location == "United Kingdom",
            ),
            schema.OSRSWorlds.members == True,
        ):
            LOGGER.info(f"Pinging {world.world_url}...")
            ping: float = requests.get(world.world_url).elapsed.total_seconds()
            players = worlds_df.loc[
                worlds_df["world_id"] == world.world_id, "players"
            ].values[0]
            ping_data = schema.PingData(
                world_id=world.world_id,
                timestamp=pd.Timestamp.now(),
                ping=ping,
                players=int(players),
            )
            session.add(ping_data)
            LOGGER.info(
                f"Pinged {world.world_url} with {ping} seconds and {players} players"
            )
            # wait for a second to not spam the server
            time.sleep(0.5)
        session.commit()
    LOGGER.info(
        f"Fetched {len(worlds)} worlds and pinged {len(worlds_to_insert)} members worlds in Germany or United Kingdom"
    )
