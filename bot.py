''' bot.py

    Grabs the latest count and list of identifiers add to the Arctic Data
    Center and pastes them into the #arctic Slack channel. Also creates tickets
    in RT for any registry-created objects that don't have tickets.
'''


import sys
import os.path
import json
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET
import requests
import requests.sessions
from dotenv import load_dotenv
import rt
import re

# Environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

LASTFILE_PATH = os.environ.get("LASTFILE_PATH")
MN_BASE_URL = os.environ.get("MN_BASE_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
RT_URL = os.environ.get("RT_URL")
RT_USER = os.environ.get("RT_USER")
RT_PASS = os.environ.get("RT_PASS")

# Token handling code: Try to load the token at bot initialization
# and leave it set to None if the token file is not found or not readable
TOKEN_PATH = os.environ.get("TOKEN_PATH")
TOKEN = None
TOKEN_PATH_FULL = os.path.join(os.path.dirname(__file__), TOKEN_PATH)

if os.path.exists(TOKEN_PATH_FULL):
    with open(TOKEN_PATH_FULL, 'rb') as f:
        TOKEN = f.read().decode('utf-8')

if TOKEN is None:
    raise Exception("Token was not readable, stopping bot operation.")

# Log in to RT
TRACKER = rt.Rt("{}/REST/1.0/".format(RT_URL), RT_USER, RT_PASS)

if TRACKER.login() is False:
    send_message("I failed to log into RT. Something's wrong!")
    raise Exception("Failed to log in to RT.")

# Hard-coded variables
PID_STARTSWITH = "arctic-data."
PID_STARTSWITH_ALT = "autogen."
EML_FMT_ID = "eml://ecoinformatics.org/eml-2.1.1"


# General functions

def get_last_run():
    last_run = None

    path = os.path.join(os.path.dirname(__file__), LASTFILE_PATH)

    if os.path.isfile(path):
        with open(path, "r") as f:
            file_content = f.read()

            if len(file_content) > 0:
                last_run = datetime.strptime(file_content, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    if last_run is None:
        last_run = datetime.utcnow()

    return last_run


def save_last_run(to_date):
    with open(os.path.join(os.path.dirname(__file__), LASTFILE_PATH), "w") as f:
        f.write(to_date.isoformat())


# Slack functions

def send_message(message):
    return requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': message}))


def test_slack():
    """Send a test message to slack."""

    print("Sending a test message...")

    r = requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': "Testing"}))

    if r.status_code != 200:
        print("Status: {}".format(r.status_code))
        print("Response: {}".format(r.text))

    return r

def create_tickets_message(metadata_pids, tickets):
    message = "The following Objects were just created or updated:\n"

    for pid,ticket in zip(metadata_pids, tickets):
        ticket_info = TRACKER.get_ticket(ticket)
        ticket_url = "{}/Ticket/Display.html?id={}".format(RT_URL, ticket)
        line = "- {} ({}) <{}|{}>\n".format(pid, get_last_name(pid), ticket_url, ticket_info['Subject'])
        message += line

    return message


# Member Node functions

def list_objects(from_date, to_date):
    url = ("{}/object?fromDate={}&toDate={}").format(MN_BASE_URL, from_date.strftime("%Y-%m-%dT%H:%M:%SZ"), to_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    response = requests.get(url)

    try:
        xmldoc = ET.fromstring(response.content)
    except ET.ParseError as err:
        print("Error while parsing list_objects() response.")
        print("Error: {}".format(err))
        print("Response content:")
        print(response.content)

        raise

    return xmldoc


def get_count(doc):
    attrs = doc.findall('.')[0].items()
    count = [attr[1] for attr in attrs if attr[0] == 'count'][0]

    return int(count)


def get_object_identifiers(doc):
    return [o.find('identifier').text for o in doc.findall("objectInfo")]


def get_metadata_pids(doc):
    metadata = []

    # Filter to EML 2.1.1 objects
    for o in doc.findall("objectInfo"):
        format_id = o.find('formatId').text
        pid = o.find('identifier').text

        if format_id == EML_FMT_ID and (pid.startswith(PID_STARTSWITH) or pid.startswith(PID_STARTSWITH_ALT)):
            metadata.append(o.find('identifier').text)

    return metadata


def get_dataset_title(pid):
    # Stop now if the token isn't set up
    if TOKEN is None:
        return None

    # Grab the doc
    req = requests.get("/".join([MN_BASE_URL, 'object', pid]),
                        headers = { "Authorization" : " ".join(["Bearer", TOKEN]) })
    if req.status_code != 200:
        return None

    doc = ET.fromstring(req.text)
    titles = doc.findall(".//title")

    if len(titles) < 1:
        return None
    else:
        return elide_text(titles[0].text, 50)


def elide_text(text, at=50):
    out = text[0:at]

    if len(text) > at:
        out = out + '...'

    return out


# RT functions

def ticket_find(pid):
    # Strip version stringn from PID
    # i.e. arctic-data.X.Y => arctic-data.X
    # so a new ticket isn't created for updates
    tokens = pid.split('.')
    pid_noversion = '.'.join(tokens[0:(len(tokens)-1)])

    title = '{}'.format(pid_noversion)
    results = TRACKER.search(Queue='arcticdata', Subject__like=title)
    ids = [t['id'].replace('ticket/', '') for t in results]

    if len(ids) > 0:
        return ids[0]
    else:
        return None


def ticket_create(pid):
    # Try to get extra metadata about the pid
    title = get_dataset_title(pid)
    last_name = get_last_name(pid)

    # Produce a nicer title in the event submitter or title are None

    # title + PID
    if title is not None and last_name is None:
        subject = "{} ({})".format(title, pid)
    # last_name + PID
    elif title is None and last_name is not None:
        subject = "{} ({})".format(last_name, pid)
    # last_name + title + PID
    elif title is not None and last_name is not None:
        subject = "{}: {} ({})".format(last_name, title, pid)
    else:
        subject = pid

    ticket = TRACKER.create_ticket(Queue='arcticdata',
                                   Subject=subject,
                                   Text=create_ticket_text(pid))

    return ticket


def create_ticket_text(pid):
    template = """A new submission just came in. View it here: https://arcticdata.io/catalog/#view/{}. This ticket was automatically created by the submissions bot because the PID {} was created/modified. See https://github.nceas.ucsb.edu/KNB/arctic-data/blob/master/docs/handling-submissions.md for more information on what to do. If you aren't sure why this ticket was created, please see the README at https://github.nceas.ucsb.edu/KNB/submissions-bot.")"""

    return template.format(pid, pid)


def ticket_reply(ticket_id, identifier):
    TRACKER.comment(ticket_id,
                    text="PID {} was updated and needs moderation. If you aren't sure why this comment was made, please see the README at https://github.nceas.ucsb.edu/KNB/submissions-bot.".format(identifier))


def create_or_update_tickets(identifiers):
    tickets = []

    if len(identifiers) <= 0:
        return tickets

    for identifier in identifiers:
        ticket = ticket_find(identifier)

        if ticket is None:
            tickets.append(ticket_create(identifier))
        else:
            ticket_reply(ticket, identifier)
            tickets.append(ticket)

    return tickets


def get_sysmeta_submitter(pid):
    if TOKEN is None:
        return None

    req = requests.get("/".join([MN_BASE_URL, 'meta', pid]),
                        headers = { "Authorization" : " ".join( ["Bearer", TOKEN] )})

    if req.status_code != 200:
        return None

    doc = ET.fromstring(req.text)
    submitters = doc.findall(".//submitter")

    if len(submitters) < 1:
        return None
    else:
        return submitters[0].text


def get_last_name(pid):
    last_name = None

    # Try to get the sysmeta submitter
    submitter = get_sysmeta_submitter(pid)

    if submitter is None:
        return None

    if re.search('orcid', submitter):
        last_name = get_last_name_orcid(submitter)
    elif submitter.lower().startswith('uid='):
        last_name = get_last_name_dn(submitter)

    return last_name


def get_last_name_dn(subject):
    '''todo'''
    tokens = dict([part.lower().split('=') for part in subject.split(',')])

    if 'uid' in tokens:
        return tokens['uid']
    else:
        return subject


def get_last_name_orcid(subject):
    orcid_id = parse_orcid_id(subject)
    
    req = requests.get("/".join(["http://pub.orcid.org", orcid_id]),
                       headers={'Accept':'application/orcid+json'})
    
    if req.status_code != 200:
        return subject

    resp = req.json()

    return resp['orcid-profile']['orcid-bio']['personal-details']['family-name']['value']


def parse_orcid_id(value):
    match = re.search("\d{4}-\d{4}-\d{4}-[\dX]{4}", value)

    if match is None:
        return value
    else:
        return match.group(0)


def get_tickets_with_new_incoming_correspondence(after):
    # RT search uses local time whereas the API uses UTC. Go figure.
    after_localtime = after.astimezone(pytz.timezone('America/Los_Angeles'))

    # Start by getting recently updated tickets
    tickets = TRACKER.search(Queue='arcticdata',
                             order='LastUpdated',
                             LastUpdated__gt=after_localtime.strftime("%Y-%m-%d %H:%M:%S"))

    # Filter to just those with new correspondence
    # from someone other than us in since LASTRUN
    return [get_recent_incoming_correspondence(ticket, after) for ticket in tickets]


def get_recent_incoming_correspondence(ticket, after):
    ticket_id = re.search(r'\d+', ticket['id']).group(0)
    correspondences = []

    session = requests.session()
    req = session.post(RT_URL, data = { 'user': RT_USER, 'pass': RT_PASS })

    if req.status_code != 200:
        raise Exception("Failed to log into RT.")

    req = session.get("{}/REST/1.0/ticket/{}/history".format(RT_URL, ticket_id))

    if req.status_code != 200:
        raise Exception("Failed to get ticket history.")

    incoming = [corr for corr in req.content.decode('utf-8').split('\n') if re.search(r'\d+: Correspondence added by .+@.+', corr) or re.search(r'\d+: Ticket created by .+@.+', corr)]    

    if len(incoming) == 0:
        return correspondences

    for inc in incoming:
        inc_id_match = re.match(r'^(\d+)', inc)

        if inc_id_match is None:
            raise Exception("Failed to extract ticket ID from correspondence.")

        req = session.get("{}/REST/1.0/ticket/{}/history/id/{}".format(RT_URL, ticket_id, inc_id_match.group(0)))

        if req.status_code != 200:
            raise Exception("Failed to get ticket history detail.")

        transaction = parse_rt_transaction(req.content.decode('utf-8'))

        if transaction['Created'] <= after:
            continue
        
        correspondences.append(format_history_entry(transaction))

    return correspondences


def parse_rt_transaction(transaction):
    lines = transaction.split('\n')
    msg = {}
    
    for i in range(len(lines)):
        line = lines[i]

        if line.startswith('id: '):
            msg['id'] = line.split(': ')[1]
        elif line.startswith('Ticket: '):
            msg['Ticket'] = line.split(': ')[1]
        elif line.startswith('Creator: '):
            msg['Creator'] = line.split(': ')[1]
        elif line.startswith('Created: '):
            msg['Created'] = parse_rt_datetime(line.split(': ')[1])
        elif line.startswith('Type: '):
            msg['Type'] = line.split(': ')[1]
        elif line.startswith('Content: '):
            content_lines = []
            i = i+1

            while( not re.search(r'\w: ', lines[i])):
                content_lines.append(lines[i])
                i = i+1

            msg['Content'] = re.sub(r'\W{2,}', ' ', ''.join(content_lines))


    return msg


def parse_rt_datetime(value):
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)


def format_history_entry(msg, trunc_at=120):
    if len(msg['Content']) > trunc_at:
        ellipsis = '...'
    else:
        ellipsis = ''
    
    if msg['Type'] == 'Correspond':
        msg['Type'] = 'Correspondence'
    elif msg['Type'] == 'Create':
        msg['Type'] = 'Ticket created'

    return "{} by {}: \"{}{}\" on <{}/Ticket/Display.html?id={}|Ticket {}>".format(msg['Type'], msg['Creator'], msg['Content'][0:(trunc_at-1)], ellipsis, RT_URL, msg['Ticket'], msg['Ticket'])


def main():
    # Process arguments
    args = sys.argv

    if len(args) == 2:
        if args[1] == "-t" or args[1] == "--test":
            test_slack()

            return

    from_date = get_last_run()
    to_date = datetime.utcnow()

    # Notify about new submissions/updates
    doc = list_objects(from_date, to_date)
    
    if get_count(doc) > 0:
        metadata_pids = get_metadata_pids(doc)
        tickets = create_or_update_tickets(metadata_pids)

        if len(tickets) > 0:
            send_message(create_tickets_message(metadata_pids, tickets))

    # Notify about new correspondences
    tickets = get_tickets_with_new_incoming_correspondence(from_date)

    for ticket in tickets:
        for corr in ticket:
            send_message(corr)

    save_last_run(to_date)


if __name__ == "__main__":
    main()
