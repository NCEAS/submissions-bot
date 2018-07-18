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
  - [pytz](https://github.com/newvem/pytz)

## Setup

- Run `pip install -r requirements.txt`
- Create a file called `.env` in the same directory as the script

  Include the following variables:

  ```text
  LASTFILE_PATH=LASTRUN                               # Determines where the bot stores its state
  MNBASE_URL="https://example.com/metacat/d1/mn/v2"   # Member Node base URL
  SLACK_WEBHOOK_URL="{URL}"                           # Your Slack webhook URL
  RT_URL="https://example.com/rt"                     # The URL of your RT install
  RT_USER="your_rt_user"                              # Your RT username
  RT_PASS="your_rt_passwrd"                           # Your RT password
  RT_TICKET_OWNER="someone"                           # RT username to assign new tickets to
  TOKEN_PATH=./token                                  # Path to a DataONE authentication token
  ```

## Running

Run `python bot.py`

## Developing & Testing

The bot is super hard to test.
This is partly because of how it was coded and also partly because it depends on the state of whichever Metacat and RT instance you point it to.

Some of the techniques I use to test the bot as I develop are:

- I keep a local copy of the `.env` file so the bot can be run locally. At the time of writing, the bot needs to be able to log into RT to start up at all.
- I usually test under iPython with the autoreload magic
  1. Start iPython with:
  
  ```sh
  $ ipython
  ```
  2. Turn on autoreload

  ```python
  %loadext autoreload
  %autoreload 2
  ```

  3. Run whatever function you want to test, being careful not to run `main()` unless you mean to

I often want to test behavior that involves the bot seeing Objects modified within a certain time period.
I manipulate the LASTRUN file as needed and usually can't remember the format it uses which is `%Y-%M-%dT%H:%H:%S`, e.g., `2018-07-17T23:05:01.744732`.