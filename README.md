# Old School RuneScape World Scraper

This Python script scrapes the Old School RuneScape (OSRS) world list and stores the data in a SQLite database. It is currently hard coded to ping all member worlds located in Germany or the United Kingdom and stores the ping data and player count. A simple addition would be to make this take command line arguments to specify which countries to ping, or read a configuration file.

## Dependencies

The script uses the following Python libraries:

- `requests` for making HTTP requests
- `bs4` (BeautifulSoup) for parsing HTML
- `pandas` for data manipulation
- `sqlalchemy` for database operations

## How it works

The script first sends a GET request to the OSRS world list page and parses the HTML response using BeautifulSoup. It then extracts the world list table and converts it into a pandas DataFrame.

The DataFrame is processed to extract and format the necessary data, such as world ID, world URL, membership status, and player count. The processed data is then converted into a list of dictionaries.

The script then creates a SQLite database (if it doesn't exist) and inserts the world data into the `OSRSWorlds` table. If a world already exists in the database, it is not inserted again.

Finally, the script pings all member worlds located in Germany or the United Kingdom and stores the ping data and player count in the `PingData` table.

## Usage

Run the script with the command `python run.py`.

## Logging

The script logs its operations to both the console and a rotating log file (`logs/world_scraper.log`). The log file has a maximum size of 100KB and keeps the last 5 backups.

## Database Schema

The database schema is defined in the `utils/schema.py` file. It consists of two tables: `OSRSWorlds` and `PingData`.

## Improvements

The script could easily be improved in the following ways:

- Make the countries to ping configurable via command line arguments or a configuration file.
- Add error handling for HTTP requests and database operations.
- Add more detailed logging and error messages.
- Add a scheduler to run the script at regular intervals.
- Instead of casting to list then back to DataFrame from the get_worlds function, we could just return the DataFrame and use it directly in the insert_worlds function. This would save some processing time and memory, but it's not a big deal for the current number of worlds and list of dictionaries is convenient for the insert function.
