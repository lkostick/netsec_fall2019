import datetime
import os
import csv


def add_connection(team_number, time):
    print('A new connection is being added for team {} at {}'.format(team_number, time))
    write_header = True
    if os.path.isfile('connections.csv'):
        write_header = False
    with open('connections.csv', 'a') as csvfile:
        fieldnames = ['team_number', 'time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow({'team_number': team_number, 'time': time})
    print('A new connection is being added for team {}'.format(team_number))
    return team_number


def add_payment(team_number, time):
    write_header = True
    print('A new payment is being added for team {} at {}'.format(team_number, time))
    if os.path.isfile('payments.csv'):
        write_header = False
    with open('payments.csv', 'wa') as csvfile:
        fieldnames = ['team_number', 'time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow({'team_number': team_number, 'time': time})


add_connection('1', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))