import datetime
import os.path
import pandas as pd
import numpy as np
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']
DATE_LAST_FROST = datetime.datetime(2023, 4, 10, 8, 0, 0)
DATE_FIRST_FROST = datetime.datetime(2023, 10, 29, 8, 0, 0)
TIMEZONE = 'America/Chicago'
EMAIL_ADDRESS = ''
CALENDAR_NAME = ''

def get_creds():
    """
    Modified the basic usage of the Google Calendar API
    Returns the service that will allow for working with Google Calendar
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print('An error occurred: %s' % error)

def get_calendars(service):
    return service.CalendarList.list()

def get_garden_calendar(calendar_list, name = CALENDAR_NAME):
    '''
    Looks for the Google calendar by the friendly name
    Returns the api response for only that calendar
    '''
    for calendar in calendar_list['items']:
        if calendar['summary'] == name:
            return calendar

def add_calendar_event(calendar_id, email_address, event_name, start_date, end_date):
    '''
    Creates the Google calendar event
    No return - sends to Google API to finish processing
    '''
    event = {
        'summary': event_name,
        'location': 'Garden',
        'description': '',
        'start': {
            'dateTime': start_date,
            'timeZone': 'America/Chicago',
        },
        'end': {
            'dateTime': end_date,
            'timeZone': 'America/Chicago',
        },
        'attendees': [
            {'email': email_address}
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
            {'method': 'email', 'minutes': 24 * 60},
            {'method': 'popup', 'minutes': 10},
            ],
        }
    }
    
    event = service.events().insert(calendarId=calendar_id, body=event).execute()

if __name__ == "__main__":
    service = get_creds()
    calendar_list = service.calendarList().list(pageToken=None).execute()
    garden_calendar = get_garden_calendar(calendar_list)

    DATE_LAST_FROST = pytz.timezone(TIMEZONE).localize(DATE_LAST_FROST)
    DATE_FIRST_FROST = pytz.timezone(TIMEZONE).localize(DATE_FIRST_FROST)

    df = pd.read_csv('garden_scheduler.csv')

    # Processes datetimes in preparation
    df['Seed Start Date'] = pd.to_datetime(DATE_LAST_FROST) - pd.TimedeltaIndex(df['Seed Start Weeks'], unit='w')
    df['Transplant Date'] = pd.to_datetime(DATE_LAST_FROST) - pd.TimedeltaIndex(df['Transplant Start Weeks'], unit='w')
    df['Event Name'] = 'Plant ' + df['Vegetable'] + " (" + df['Season'] + " " + df['Seed Start'] + ")"
    df['Transplant Event Name'] = np.where(
        ~ pd.isna(df['Transplant Date']), 
        'Transplant ' + df['Vegetable'] + " (" + df['Season'] + " " + df['Seed Start'] + ")",
        np.nan
    )

    df['Event Time End'] = df['Seed Start Date'] + pd.Timedelta(3, 'h')

    df['Event Time'] = df['Seed Start Date'].map(lambda x: x.isoformat())
    df['Event Time End'] = df['Event Time End'].map(lambda x: x.isoformat())
    df['Transplant Event Time'] = df['Transplant Date'].map(lambda x: x.isoformat())

    df.apply(
        lambda row: add_calendar_event(garden_calendar['id'], EMAIL_ADDRESS, row['Event Name'], row['Event Time'], row['Event Time End']),
        axis = 1
    )