"""A module for looking at who is waiting and where and what needs to be done.
"""

import logging
from time import strptime, mktime
from datetime import datetime, timedelta
from termcolor import colored

import rtclient

# constants for customer logic
CUSTOMER = 0
STAFF    = 1

def waiting_n(tickets, histories, teams):
    '''batch processing for finding who tickets are waiting on'''
    logging.debug("waiting_n:\ntickets:\n{0}".format(tickets)) #debug

    owners = []
    queues = []
    for ticket in tickets:
        owners.append(ticket["Owner"])
        queues.append(ticket["Queue"])
    waiting = []

    logging.debug("owners:\n{0}".format(owners)) #debug
    logging.debug("queues:\n{0}".format(queues)) #debug
   
    index = 0
    for history in histories:
        logging.debug("histories:\n{0}".format(history)) #debug
        not_found = True
        reverse_counter = -1
        meaningful_line = ''
        while not_found:
            if history[reverse_counter] == '':
                reverse_counter -= 1
            else:
                meaningful_line = history[reverse_counter]
                not_found = False
                break
        if owners[index] in meaningful_line:
            waiting.append(CUSTOMER)
        elif owners[index] is 'Nobody':
            teamname = teams.get_team(queues[index])
            if teams.has_user(teamname, meaningful_line):
                waiting.append(CUSTOMER)
            else:
                waiting.append(STAFF)
        else:
            waiting.append(STAFF)
        index += 1

    return waiting

def health_n(tickets, states, waitings):
    '''batch processing for finding the health of tickets'''
    healths = []
    ticket_index = 0
    for ticket in tickets:
        updated = datetime.fromtimestamp(mktime(strptime(ticket['LastUpdated'],
            rtclient.TICKET_TIME)))
        #created = datetime.fromtimestamp(mktime(strptime(ticket['Created'],
        #    rtclient.TICKET_TIME)))

        logging.debug("\nLastUpdated: {0},\ntype LastUpdated: {1}"
            .format(ticket["LastUpdated"],type(ticket["LastUpdated"]))) #debug

        logging.debug("\nmktime: {0},\ntype mktime: {1}"
            .format(mktime(strptime(ticket['LastUpdated'], 
                rtclient.TICKET_TIME)),
                type(mktime(strptime(ticket['LastUpdated'],
                rtclient.TICKET_TIME))))) #debug

        logging.debug("\nupdated: {0},\ntype updated: {1}"
            .format(updated,type(updated))) #debug

        age = datetime.now() - updated
        ticket_string = "{0}: {1}, {2}. Status: {3}".format(
                ticket['id'],
                ticket['Subject'][:25], 
                strfdelta(age, "{days} days {hours}:{minutes}:{seconds}"), 
                ticket['Status']
                )

        if not isinstance(states[ticket['Status'].lower()], dict):
            healths.append("No policy specified for: {0}"
                .format(ticket_string))
        else:
            status = ticket['Status'].lower()
            policy = dict(states[ticket['Status'].lower()])

            # default for activity_Attr...
            activity_attr = 'updated'
       
            # what standard are we holding this ticket to?
            if isinstance(policy, dict):
                activity_attr, speeds = policy.popitem()

            # last activity is judged by the LastUpdated or 
            #Created or other attrs
            #last_active = activity_attr

            # and it needs?
            needs = __adj2needs__[activity_attr].format(ticket['Queue'])

            deadline = _deadline(speeds, updated)

            logging.debug('deadline: %s', deadline) #debug

            ticktxt = colored(ticket_string, 'white', attrs=['bold'])
            needs = colored(needs, 'white')
        
            #if deadline > datetime.now():
            if not _overdue(deadline):
                status = colored("On Time {1}: ", 'green')
            else:
                if waitings[ticket_index] == CUSTOMER:
                    #if we're already in a stalled state print in blue
                    if status == 'stalled':
                        logging.debug('float(age.days): %s', 
                            str(age.days)) #debug
                        if float(age.days) < (speeds['slow']/24.0):
                            status = colored(
                                "Waiting on Customer (ticket stalled) {1}: ",
                                'yellow')
                        else:
                            status = colored(
                                "Ticket should be expired {1}: ",
                                'grey')

                    #if we're not in stalled state, should we be?
                    else:
                        logging.debug('age.days: %s', str(age.days)) #debug
                        if age.total_seconds() < speeds['slow']*60*60:
                            status = colored("Waiting on Customer {1}: ",
                                'blue')
                        else:
                            status = colored(
                                "Should be moved to 'stalled' status {1}: ",
                                'cyan')

                else:
                    needs = colored(
                        '{0}'.format(needs), 'magenta', attrs=['underline'])
                    status = colored("Overdue {1}: ", 'red')

        msg = status + ticktxt + ' ' + needs
        ticket_index += 1
        healths.append( msg.format(needs, deadline) )
    return healths

def _deadline(speeds, last_active):
    '''get the deadline for the ticket'''
    # what is fast and what is slow? casts config vals to time deltas
    _, slow = [timedelta(hours=speeds[n]) #first var would be 'fast'
                 for n in speeds.iterkeys()]
    # we ought to be done before this one
    deadline = last_active + slow
    return deadline

def _overdue(deadline):
    '''check if it's overdue at the moment'''
    if deadline < datetime.now():
        return True
    else:
        return False

__adj2needs__ = {
    'created': 'needs update from {0} POC',
    'updated': 'needs checkin from customer or {0} POC',
    }

def strfdelta(tdelta, fmt):
    '''method taken from: 
    http://stackoverflow.com/questions/8906926/
        formatting-python-timedelta-objects
    becuz timedeltas are terrible, and they should be changed.'''
    delta = {"days": tdelta.days}
    delta["hours"], rem = divmod(tdelta.seconds, 3600)
    delta["minutes"], delta["seconds"] = divmod(rem, 60)
    return fmt.format(**delta)
