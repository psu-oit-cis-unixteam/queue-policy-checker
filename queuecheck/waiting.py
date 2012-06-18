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

class Ticket(object):
    """Describes a ticket and it's freshness"""

    adj2needs = {
                'created': 'needs update from {0.queue} POC',
                'updated': 'needs checkin from customer or {0.queue} POC',
                }

    def __init__(self, ticket_id, creds, url, states, teams):
        self.ticket_id = ticket_id
        self.ticket_dict = rtclient.get(ticket_id, creds, url)
        
        # copy the pertinent details up a level
        self.created   = self.ticket_dict.get('Created')
        self.queue     = self.ticket_dict.get('Queue')
        self.status    = self.ticket_dict.get('Status')
        self.subject   = self.ticket_dict.get('Subject')
        self.updated   = self.ticket_dict.get('LastUpdated')
        self.owner     = self.ticket_dict.get('Owner')
        self.requestor = self.ticket_dict.get('Requestors')
        self.creds     = creds
        self.url       = url
        self.teams     = teams

        logging.debug(
                'requestor for the following ticket: {0}'.format(
                    self.requestor)) #debug

        # cast the time fields to usable types
        for timetype in ['updated', 'created']:
            time = getattr(self, timetype)
            time = mktime(strptime(time, rtclient.TICKET_TIME))
            setattr(self, timetype, datetime.fromtimestamp(time))

        try:
            # a copy of whatever policy is applicable to this ticket's status
            self.policy = states[self.status.lower()].copy()
        except KeyError:
            self.policy = False
            logging.info("No '{0.status}' policy specified.".format(self))

        # default for activity_Attr...
        activity_attr = 'updated'
        
        # what standard are we holding this ticket to?
        if isinstance(self.policy, dict):
            activity_attr, self.speeds = self.policy.popitem()

        # last activity is judged by the LastUpdated or Created or other attrs
        self.last_active = getattr(self, activity_attr)
        logging.critical('SELF.LAST_ACTIVE:{0}\nTYPE(SELF.LAST_ACTIVE:{1}'.format(self.last_active,type(self.last_active)))     
        # and it needs?
        self.needs = self.adj2needs[activity_attr].format(self)

    def __str__(self):
        return '{0.ticket_id}: {0.subject}, {0.age}. Status: {0.status}'.format(self)
    
    @property
    def age(self):
        '''get the age when requested'''
        return datetime.now() - self.last_active

    @property
    def overdue(self):
        '''check if it's overdue at the moment'''
        if self.deadline < datetime.now():
            return True
        else:
            return False

    @property
    def deadline(self):
        '''get the deadline for the ticket'''
        # what is fast and what is slow? casts config vals to time deltas
        fast, slow = [timedelta(hours=self.speeds[n])
                     for n in self.speeds.iterkeys()]
        # we ought to be done before this one
        deadline = self.last_active + slow
        return deadline

    @property
    def waiting(self):
        '''waiting will look at the ticket's history and compare to the owner of the ticket;
        if they're different, then it will be assumed that we are waiting on the owner.'''
        #query the ticket's history and split on newlines
        history = rtclient.history(self.ticket_id, self.creds, self.url).text
        hist_lines = history.split('\n')

        #iterate backwards from the end of the history till you get to the first line that
        #isn't empty
        not_found = True
        reverse_counter = -1
        meaningful_line = ''
        while not_found:
            if hist_lines[reverse_counter] == '':
                reverse_counter -= 1
            else:
                meaningful_line = hist_lines[reverse_counter]
                not_found = False

        #if the owner's name is in the non-empty line, then we are waiting on the customer
        if self.owner in meaningful_line:
            return CUSTOMER
        #elif covers the case when there's no current owner, was the last person who touched
        #ticket in the right team?
        elif self.owner is 'Nobody':
            teamname = self.teams.get_team(self.queue)
            if self.teams.has_user(teamname, meaningful_line):
                return CUSTOMER
            else:
                return STAFF

    def health(self):
        """Perform some date math and return a pretty status string."""
        if not isinstance(self.policy, dict):
            return "No policy specified for: {0}".format(self)

        details = (self, self.deadline)
        logging.info('self.deadline: %s', self.deadline)

        ticktxt = colored(str(self), 'white', attrs=['bold'])
        needs = colored('{0.needs}', 'white')
        
        #if deadline > datetime.now():
        if not self.overdue:
            status = colored("On Time {1}: ", 'green')
        else:
            if self.waiting == CUSTOMER:
                #if we're already in a stalled state print in blue
                if self.status == 'stalled':
                    logging.info('float(self.age.days): %s', str(self.age.days))
                    if float(self.age.days) < (self.speeds['slow']/24.0):
                        status = colored("Waiting on Customer (ticket stalled) {1}: ",'yellow')
                    else:
                        status = colored("Ticket should be expired {1}: ",'grey')
                #if we're not in stalled state, should we be?
                else:
                    logging.info('self.age.days: %s', str(self.age.days))
                    if self.age.total_seconds() < self.speeds['slow']*60*60:
                        status = colored("Waiting on Customer {1}: ",'blue')
                    else:
                        status = colored("Should be moved to 'stalled' status {1}: ",'cyan')
            else: 
                needs = colored('{0.needs}', 'magenta', attrs=['underline'])
                status = colored("Overdue {1}: ", 'red')

        msg = status + ticktxt + ' ' + needs
        return msg.format(*details)

def waiting_n(tickets, creds, url, states, teams, batch_size):
    '''batch processing for finding who tickets are waiting on'''
    logging.debug("waiting_n:\ntickets:\n{0}".format(tickets)) #debug

    histories, owners, queues = rtclient.history_n(tickets, creds, url, batch_size)
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

def health_n(tickets, creds, url, states, teams, waitings, batch_size):
    '''batch processing for finding the health of tickets'''
    healths = []
    ticket_index = 0
    for ticket in tickets:
        updated = datetime.fromtimestamp(mktime(strptime(ticket['LastUpdated'], rtclient.TICKET_TIME)))
        created = datetime.fromtimestamp(mktime(strptime(ticket['Created'], rtclient.TICKET_TIME)))

        logging.debug("\nLastUpdated: {0},\ntype LastUpdated: {1}".format(ticket["LastUpdated"],type(ticket["LastUpdated"]))) #debug
        logging.debug("\nmktime: {0},\ntype mktime: {1}".format(mktime(strptime(ticket['LastUpdated'], rtclient.TICKET_TIME)),type(mktime(strptime(ticket['LastUpdated'], rtclient.TICKET_TIME))))) #debug
        logging.debug("\nupdated: {0},\ntype updated: {1}".format(updated,type(updated))) #debug

        age = datetime.now() - updated
        ticket_string = "{0}: {1}, {2}. Status: {3}".format(
                ticket['id'],
                ticket['Subject'][:25], 
                strfdelta(age, "{days} days {hours}:{minutes}:{seconds}"), 
                ticket['Status']
                )

        if not isinstance(states[ticket['Status'].lower()], dict):
            healths.append( "No policy specified for: {0}".format(ticket_string) )
        else:
            status = ticket['Status'].lower()
            policy = dict(states[ticket['Status'].lower()])

            # default for activity_Attr...
            activity_attr = 'updated'
       
            # what standard are we holding this ticket to?
            if isinstance(policy, dict):
                activity_attr, speeds = policy.popitem()

            # last activity is judged by the LastUpdated or Created or other attrs
            last_active = activity_attr

            # and it needs?
            needs = _adj2needs[activity_attr].format(ticket['Queue'])

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
                        logging.debug('float(age.days): %s', str(age.days)) #debug
                        if float(age.days) < (speeds['slow']/24.0):
                            status = colored("Waiting on Customer (ticket stalled) {1}: ",'yellow')
                        else:
                            status = colored("Ticket should be expired {1}: ",'grey')

                    #if we're not in stalled state, should we be?
                    else:
                        logging.debug('age.days: %s', str(age.days)) #debug
                        if age.total_seconds() < speeds['slow']*60*60:
                            status = colored("Waiting on Customer {1}: ",'blue')
                        else:
                            status = colored("Should be moved to 'stalled' status {1}: ",'cyan')

                else:
                    needs = colored('{0}'.format(needs), 'magenta', attrs=['underline'])
                    status = colored("Overdue {1}: ", 'red')

        msg = status + ticktxt + ' ' + needs
        ticket_index += 1
        healths.append( msg.format(needs, deadline) )
    return healths

def _deadline(speeds, last_active):
    '''get the deadline for the ticket'''
    # what is fast and what is slow? casts config vals to time deltas
    fast, slow = [timedelta(hours=speeds[n])
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

_adj2needs = {
    'created': 'needs update from {0} POC',
    'updated': 'needs checkin from customer or {0} POC',
    }

def strfdelta(tdelta, fmt):
    '''method taken from: http://stackoverflow.com/questions/8906926/formatting-python-timedelta-objects
    becuz timedeltas are terrible, and they should be changed.'''
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)
