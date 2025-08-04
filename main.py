import requests
import time
import smtplib
from twilio.rest import Client
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path="hey.env")
SHEETY_API = os.getenv("SHEETY_API")
API_KEY = os.getenv("AMADEUS_API_KEY")
API_SECRET = os.getenv("AMADEUS_API_SECRET")
ACC_SID = os.getenv("TWILIO_ACC_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
USER_SHEET_ENDPOINT = os.getenv("FORM_GET_API")
MY_EMAIL = os.getenv("MY_EMAIL")
PASSWORD = os.getenv("PASSWORD")
auth_headers = {"Content-Type": "application/x-www-form-urlencoded"}
auth_data = {
    "grant_type": "client_credentials",
    "client_id": API_KEY,
    "client_secret": API_SECRET
}
auth_response = requests.post(
    url="https://test.api.amadeus.com/v1/security/oauth2/token",
    headers=auth_headers,
    data=auth_data
)
access_token = auth_response.json().get('access_token')
api_headers = {"Authorization": f"Bearer {access_token}"}
dest_response = requests.get(url=SHEETY_API)
destinations = dest_response.json().get('sheet1', [])
def iata_update(city_list):
    for entry in city_list:
        city_name = entry['city']
        try:
            iata_response = requests.get(
                url="https://test.api.amadeus.com/v1/reference-data/locations/cities",
                headers=api_headers,
                params={"keyword": city_name}
            )
            data = iata_response.json()
            if 'data' in data and data['data']:
                i_code = data['data'][0]['iataCode']
                update_body = {"price": {"iataCode": i_code}}
                requests.put(f"{SHEETY_API}/{entry['id']}", json=update_body)
        except Exception as e:
            print(f"IATA lookup failed for {city_name}: {e}")
        time.sleep(3)
def msg(city_list):
    for city in city_list:
        iata = city['iataCode']
        def get_flight_data(non_stop: str):
            params = {
                "originLocationCode": "BLR",
                "destinationLocationCode": iata,
                "departureDate": datetime.now().strftime('%Y-%m-%d'),
                "adults": 1,
                "nonStop": non_stop.lower(),
                "currencyCode": "GBP",
                "max": 10
            }
            response = requests.get(
                url="https://test.api.amadeus.com/v2/shopping/flight-offers",
                headers=api_headers,
                params=params
            )
            return response.json()
        response = get_flight_data("true")
        if 'meta' not in response:
            print(f"API error for {iata}: {response}")
            continue
        flight_count = response['meta'].get('count', 0)
        if flight_count == 0:
            response = get_flight_data("false")
            if 'meta' not in response:
                print(f"API error for {iata}: {response}")
                continue
            flight_count = response['meta'].get('count', 0)
        try:
            if flight_count > 0:
                offer = response['data'][0]
                segments = offer['itineraries'][0]['segments']
                stops = len(segments) - 1
                arrival_code = segments[-1]['arrival']['iataCode']
                grand_total = round(float(offer['price']['grandTotal']))
                ticket_date = offer['lastTicketingDate']
                if int(city['lowestPrice']) > grand_total:
                    message = (
                        f"-Low price alert! Only £{grand_total} to fly from BLR to "
                        f"{arrival_code} on {datetime.now().date()} "
                        f"{'non stop' if stops == 0 else f'with {stops} stops'}, until {ticket_date}"
                    )
                    user_data = requests.get(USER_SHEET_ENDPOINT).json()
                    for user in user_data.get('users', []):
                        email = user['email']
                        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
                            connection.starttls()
                            connection.login(user=MY_EMAIL, password=PASSWORD)
                            connection.sendmail(
                                from_addr=MY_EMAIL,
                                to_addrs=email,
                                msg=f"Subject: Flight Deal Alert\n\n{message}"
                            )
                    # client = Client(ACC_SID, AUTH_TOKEN)
                    # client.messages.create(
                    #     from_='whatsapp:*',
                    #     body=message,
                    #     to='whatsapp:*'
                    # )
                    update_body = {
                        "sheet1": {
                            "lowestPrice": grand_total,
                            "stops": stops
                        }
                    }
                    requests.put(f"{SHEETY_API}/{city['id']}", json=update_body)
            else:
                print(f"No flights found for {iata}")
        except KeyError as e:
            print(f"KeyError: {e} for {iata}, skipping.")
msg(destinations)