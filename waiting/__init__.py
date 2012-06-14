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
        self.created   = self.ticket_dict['Created']
        self.queue     = self.ticket_dict['Queue']
        self.status    = self.ticket_dict['Status']
        self.subject   = self.ticket_dict['Subject']
        self.updated   = self.ticket_dict['LastUpdated']
        self.owner     = self.ticket_dict['Owner']
        self.requestor = self.ticket_dict['Requestors']
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
        
        # and it needs?
        self.needs = self.adj2needs[activity_attr].format(self)

    def __str__(self):
        return '{0.ticket_id}: {0.subject}, {0.age}. Status: {0.status}'.format(self)
        #return '{0.ticket_id}: {0.subject}, {0.age}'.format(self)
    
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
