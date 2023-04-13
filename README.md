# submissions-bot

Alerts a Slack channel (via webhook) of recently-modified objects from
[`listObjects()`](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) and creates tickets in
[RT](https://www.bestpractical.com/rt-and-rtir) for new submissions and comments on already-created tickets.

Note: If you're looking for deployment details about the bot, see the upkeep section below, which outlines things such as how the bot actually runs.

## How the bot works

Every ten minutes, the bot visits the Member Node's [/object](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) endpoint and asks for a list of the objects that have been modified in the last ten minutes.
Modifications include being created, updated, archived, or having a property of the object's system metadata modified (e.g., changing rights holder).
This endpoint produces a list of PIDs, which the bot checks against a [whitelist](https://cn.dataone.org/cn/v2/accounts/CN=arctic-data-admins,DC=dataone,DC=org) of admin orcid Ids, and filters out any PIDs submitted by an admin.
For each filtered PID, the bot gets the first version of the PID in the obsolescence chain, and checks RT for a ticket that contains the first version PID in its title.
For example, if the PID is 'arctic-data.1234.1', the bot looks for a ticket with 'arctic-data.1234' in the title.
The bot then creates a ticket if a matching RT ticket is not found or comments on the existing ticket if one is found.

## Dependencies

- Currently running on Python 3.10.6
- Extra packages (install via requirements.txt):
  - [requests](http://docs.python-requests.org/en/master/)
  - [python-dotenv](https://github.com/theskumar/python-dotenv)
  - [python-rt](https://gitlab.labs.nic.cz/labs/python-rt)
    - Currently requires version 2.2.2
  - [pytz](https://github.com/newvem/pytz)

The `pip freeze` output is shown below.

```
certifi==2022.12.7
charset-normalizer==3.1.0
idna==3.4
python-dotenv==1.0.0
pytz==2023.3
requests==2.28.2
requests-toolbelt==0.10.1
rt==3.0.5
urllib3==1.26.15
```

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

Another way of testing the bot would be setting `.env` up as above but just replacing what's in

```python
if __name__ == "__main__":
  main() # <--- Replace me!
```

with the code you want to test and running the bot with `python bot.py`.

# Arctic Bot Operations Manual

Hello, intrepid Arctic Bot user, and welcome to my operations manual.
Please watch your step and don't spend too much timing scratching your head if something doesn't make sense. Bryce probably forgot to document something.

## About me

I periodically poll two locations for relevant information to share in the #arcticbot Slack channel and pipe relevant information into the channel:

1. RT for new correspondences (new tickets, correspondence on existing tickets)
2. Metacat's `listObjects` endpoint for new EML Objects for new Registry submissions
    
    Note: New RT tickets are created for new EML Objects that come in through the Registry

This effectively covers our bases so we can react to new work by watching just the #arcticbot channel.

## Upkeep

I'm just a single Python 3 script and my source is located at https://github.nceas.ucsb.edu/KNB/submissions-bot.

- I live in /home/bot/submissions-bot

    ```
    mecum@arctica:~/$ ls /home/bot/submissions-bot -a1
    .
    ..
    bot.py
    .env                # deployment-specific settings
    .git
    .gitignore
    LASTRUN
    __pycache__
    README.md
    requirements.txt
    token               # a long-lived auth token
    ```

- I can be configured via the `./.env` file located in the deployment folder
- I make use of an authentication token which is stored in `./token`
- I am run every 5 minutes via cron, under the user `bot` on arcticdata.io. 
- I run in a virtual environment which can be created using `mkvirtualenv bot` `pip install -r requirements.txt`
- Below is the virtualenvwrapper config to use
```
# virtualenvwrapper config
export WORKON_HOME=$HOME/.virtualenvs
source /usr/share/virtualenvwrapper/virtualenvwrapper.sh
```
 
    Here's bot's crontab:

    ```
    MAILTO="jclark@nceas.ucsb.edu"
    */5 * * * * . /home/bot/.virtualenvs/bot/bin/activate &&  python /home/bot/submissions-bot/bot.py >> /home/bot/submissions-bot/submissions-bot.log 2>&1
    ```

### Refreshing my authentication token

If my authentication token expires (happens on a months-or-so scale), someone will need to log into arcticdata.io and update it:

```sh
$ ssh arcticdata.io
...
$ sudo -u bot -i # or some variant to get permission to write
$ cd /home/bot/submissions-bot
$ echo "{TOKEN}" > token
```

