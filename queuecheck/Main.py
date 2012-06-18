#!/usr/bin/env python

import argparse
import logging
import yaml
from getpass import getuser
from os import path

import teams
import rtclient
import waiting

def check(param_path, who=False):
    """Check statuses based on the parameters file at param_path, optionally
    constrain the search to a specific user."""

    starttime = waiting.datetime.now() #debug

    logging.debug('Opening: %s, uid=%s', param_path, who)
    with open(param_path, 'rb') as param_file:
        config = yaml.load(param_file)
  
    query = dict()

    # build the owner constraints. Command line supercedes conf file
    if who:
        query['who'] = 'Owner = "{}" and '.format(who)
    #otherwise, it will go to the conf and look for 'owner'
    else:
        #check if present and not empty in conf
        if 'owner' in config.keys() and not config['owner'] is None:
            #for multiple entries, format queries and concatenate
            if type(config['owner']) == list:
                owners = ['Owner = "{}"'.format(user)
                        for user in config['owner']]
                query['who'] = '(' + ' or '.join(owners) + ') and '
            #for single entry
            elif type(config['owner']) == str:
                query['who'] = 'Owner = "{}" and '.format(config['owner'])
        #if its not there or empty, then empty string
        else:
            query['who'] = ''

    #an error for no queues in the config
    if len(config['queues']) == 0:
        raise Exception('Error! No queues indicated in config file.')

    # build the queue constraints
    queues = ['Queue = "{}"'.format(queue) for queue in config['queues']]
    query['queue'] = ' or '.join(queues)

    #an error for no statuses in skip states
    if config['skip_states'] == None:
        logging.critical('Warning! No skip states indicated in config file.')
        query['skip_states'] = ''

    else:
        # build statuses
        skip_statuses = ['Status != "{}"'.format(status)
                        for status in config['skip_states']]
        query['skip_states'] = ' and '.join(skip_statuses)

    # get all tickets with applicable statuses from all applicable queues
    query = "{who} ({queue}) and ({skip_states})".format(**query)
    
    # make sure to always have a valid query
    if ' and ()' in query:
        query = query[:-7]
    if '()' in query:
        query = query[:query.index('()')].append(query[(query.index('()')+2):])

    logging.info('Running query: %s', query)

    teams_object = teams.Teams(config['teams'])

    my_tickets = []
    batch_size = 5

    for ticket in rtclient.search(query, config['creds'], config['url']):
        my_tickets.append(ticket)
        if len(my_tickets) >= batch_size:

            batch_tickets = rtclient.get_n(my_tickets, 
                    config['creds'], 
                    config['url'], 
                    batch_size)
            #logging.critical('batch_tickets:\n{0}'.format(batch_tickets)) #debug

            batch_waiting = waiting.waiting_n(batch_tickets, config['creds'], 
                    config['url'], config['states'], config['teams'], batch_size)
            #logging.critical('batch_waiting:\n{0}'.format(batch_waiting)) #debug

            batch_health  = waiting.health_n(batch_tickets, config['creds'], 
                    config['url'], 
                    config['states'], 
                    config['teams'], 
                    batch_waiting, 
                    batch_size)
            #logging.critical('batch_health:\n{0}'.format(batch_health)) #debug

            #for health in batch_health:
            #    print health

            #for _ticket in batch_tickets:
            #    #logging.debug( 'str(int(
            #       _ticket[\'id\'].split(\'/\')[1])): {0}'.format(
            #           str(int(_ticket['id'].split('/')[1]))) ) #debug
            #    #ticket_number = int(_ticket['id'].split('/')[1])
            #    #aticket = waiting.Ticket(
            #    #        ticket_number,
            #    #        config['creds'],
            #    #        config['url'],
            #    #        config['states'],
            #    #        teams_object)
            #    #ticket_health = aticket.health()
            #    #if ticket_health:
            #    #    pass
            #    #    #print ticket_health
            my_tickets = list()
            #print 'just did a batch'
        #logging.info('Got ticket=%s subject="%s"', *ticket)
        #ticket_n, _ = ticket
        #aticket = waiting.Ticket(
        #        ticket_n,
        #        config['creds'],
        #        config['url'],
        #        config['states'],
        #        teams_object)
        #ticket_health = aticket.health()
        #if ticket_health:
        #    print ticket_health
    endtime = waiting.datetime.now()
    total_time = endtime - starttime
    print 'total time: '+waiting.strfdelta(total_time, "{minutes}:{seconds}")

class Main():
    def __call__(self):
        """Parse args and initiate a check."""
        parser = argparse.ArgumentParser(description=__doc__)

        # default config path
        default_config = path.join(path.curdir, 'config.yaml')
        parser.add_argument('-p', '--paramfile', dest='param_path',
                            default=default_config,
                            help="Parameter file, default: %(default)s")

        parser.add_argument('-v', dest='verbosity', action='store_const',
                            const=logging.INFO, help='Verbose.')
        parser.add_argument('-vv', dest='verbosity', action='store_const',
                            const=logging.DEBUG, help='Very verbose.')

        who = parser.add_mutually_exclusive_group()
#        who.add_argument('--everyone', dest='who', action='store_false',
#            help='Check tickets owned by everyone.')
        who.add_argument('--me', dest='who', action='store_const', 
                const=getuser(), help='Check tickets owned by %(const)s')
        who.add_argument('--who', dest='who', action='store', 
                default='Nobody', 
                help='Examine tickets owned by someone, default: %(default)s')

        args = parser.parse_args()

        if args.who is None:
            pass

        logging.basicConfig(
            format='[%(levelname)s] %(asctime)s: %(message)s',
            level=args.verbosity
        )

        check(args.param_path, args.who)

QueueCheck = Main()
