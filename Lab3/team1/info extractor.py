import csv

class Team:
    def __init__(self, team_number):
        self.team_number = team_number
        self.dates = []
        self.connection_num = []
        self.pay_num = []
        self.exit_num = []

teams = []
teams.append(Team(2))
teams.append(Team(3))
teams.append(Team(4))
teams.append(Team(5))
teams.append(Team(6))
teams.append(Team(9))

with open('connections.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        team_number = row['team_number']
        time = row['time'].split(' ')[0]

