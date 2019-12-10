import csv

class Team:
    def __init__(self, team_number):
        self.team_number = team_number
        self.dates = []
        self.connection_num = []
        self.pay_num = []
        self.exit_num = []

teams = []
teams.append(Team('2'))
teams.append(Team('3'))
teams.append(Team('4'))
teams.append(Team('5'))
teams.append(Team('6'))
teams.append(Team('9'))

dates = []

with open('connections.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        team_number = row['team_number']
        time = row['time'].split(' ')[0]
        if team_number != '1':
            if time not in dates:
                dates.append(time)
            for i in teams:
                if i.team_number == team_number:
                    team = i
                    break
            date_index = None
            for i in range(len(team.dates)):
                if team.dates[i] == time:
                    date_index = i
                    break
            if date_index is None:
                team.dates.append(time)
                date_index = len(team.dates)
            if len(team.connection_num) < date_index:
                team.connection_num.append(1)
                team.exit_num.append(0)
                team.pay_num.append(0)
            else:
                team.connection_num[date_index] += 1

with open('payments.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        team_number = row['team_number']
        time = row['time'].split(' ')[0]
        if team_number != '1':
            for i in teams:
                if i.team_number == team_number:
                    team = i
                    break
            date_index = None
            for i in range(len(team.dates)):
                if team.dates[i] == time:
                    date_index = i
                    break
            if date_index is None:
                team.dates.append(time)
                date_index = len(team.dates)
            if len(team.pay_num) < date_index:
                team.pay_num.append(1)
            else:
                team.pay_num[date_index] += 1


with open('exits.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        team_number = row['team_number']
        time = row['time'].split(' ')[0]
        if team_number != '1':
            for i in teams:
                if i.team_number == team_number:
                    team = i
                    break
            date_index = None
            for i in range(len(team.dates)):
                if team.dates[i] == time:
                    date_index = i
                    break
            if date_index is None:
                team.dates.append(time)
                date_index = len(team.dates)
            if len(team.exit_num) < date_index:
                team.exit_num.append(1)
            else:
                team.exit_num[date_index] += 1

for i in dates:
    print(i)
    for j in teams:
        if i in j.dates and j.connection_num[j.dates.index(i)] > 0:
            print('\tteam' + j.team_number)
            date_index = j.dates.index(i)
            print('\t\tNumber of connections: ', j.connection_num[date_index])
            print('\t\tNumber of payments: ', j.pay_num[date_index])
            print('\t\tNumber of exits: ', j.exit_num[date_index])
        # else:
        #     print('\t\tNumber of connections: 0')
        #     print('\t\tNumber of payments: 0')
        #     print('\t\tNumber of exits: 0')

