# submissions-bot

Alerts a Slack channel (via webhook) of recently-modified objects from
[`listObjects()`](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) and creates tickets in
[RT](https://www.bestpractical.com/rt-and-rtir) for new submissions and comments on already-created tickets.

Note: If you're looking for deployment details about the bot, you might want to look at [the arctic-bot README](https://github.nceas.ucsb.edu/KNB/arctic-data/blob/master/datateam/How_To/arctic-bot.md) which outlines things such as how the bot actually runs.

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

- To try installing under Ubuntu 22.04 with python 3.7, install python from the deadsnakes PPA, then create a virtualenv for the app:

```sh
$ sudo add-apt-repository -P ppa:deadsnakes/ppa
$ sudo apt update   
$ sudo apt install python3.7
$ sudo apt install python3.7-distutils
$ mkvirtualenv -p python3.7 arcticbot
$ python -V
Python 3.7.16

$ pip3 install -r requirements.txt
$ pip3 freeze > requirements-py37.txt
$ cat requirements-py37.txt
certifi==2022.12.7
charset-normalizer==3.1.0
idna==3.4
python-dotenv==0.21.1
pytz==2023.3
requests==2.28.2
requests-toolbelt==0.10.1
rt==3.0.5
typing_extensions==4.5.0
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
