'''/queue-policy-checker'''

class Teams(object):
    '''teams class will hold the different teams as a dict
    and it will process text for team member names'''
    def __init__(self, teams_dict):
        '''init method takes the teams dict from the yaml'''
        self.teams_dict = teams_dict

    def has_user(self, teamname, text):
        '''this method iterates through text for users from the
        appropriate team.'''
        for member in self.teams_dict[teamname]:
            if member in text:
                return True
        return False

    def get_team(self, queue):
        '''this method takes the queue name as it is and gets the
        appropriate team name'''
        try:
            _ = self.teams_dict[queue]
            return queue
        except KeyError:
            for teamname in self.teams_dict.keys():
                if teamname in queue:
                    return teamname
