# submissions-bot

Alerts a Slack channel (via webhook) of recently-modified objects from
[`listObjects()`](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) and creates tickets in
[RT](https://www.bestpractical.com/rt-and-rtir) for new submissions and comments on already-created tickets.

## How the bot works

Every ten minutes, the bot visits the Member Node's [/object](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) endpoint and asks for a list of the objects that have been modified in the last ten minutes.
Modifications include being created, updated, archived, or having a property of the object's system metadata modified (e.g., changing rights holder).
This endpoint produces a list of PIDs, which the bot checks against a [whitelist](https://cn.dataone.org/cn/v2/accounts/CN=arctic-data-admins,DC=dataone,DC=org) of admin orcid Ids, and filters out any PIDs submitted by an admin.
For each filtered PID, the bot gets the first version of the PID in the obsolescence chain, and checks RT for a ticket that contains the first version PID in its title.
For example, if the PID is 'arctic-data.1234.1', the bot looks for a ticket with 'arctic-data.1234' in the title.
The bot then creates a ticket if a matching RT ticket is not found or comments on the existing ticket if one is found.

## Dependencies

- I have developed and tested this with Python 3.5.1
- Extra packages (install via requirements.txt):
  - [requests](http://docs.python-requests.org/en/master/)
  - [python-dotenv](https://github.com/theskumar/python-dotenv)
  - [python-rt](https://gitlab.labs.nic.cz/labs/python-rt)

## Setup

- Run `pip install -r requirements.txt`
- Create a file called `.env` in the same directory as the script

  Include the following variables:

  ```
  LASTFILE_PATH=LASTRUN             # Determines where the bot stores its state
  MNBASE_URL="{}"                     # Member Node base URL
  SLACK_WEBHOOK_URL="{URL}"         # Your Slack webhook URL
  RT_URL="https://your-org.com/rt"  # The URL of your RT install
  RT_USER="you"                     # Your RT username
  RT_PASS="{PASSWORD}"              # Your RT password
  RT_TICKET_OWNER="someone"         # RT username to assign new tickets to
  TOKEN_PATH=./token                # Path to a DataONE authentication token
  ```

## Running

Run `python bot.py`
