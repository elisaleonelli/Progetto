import requests
import time
import json

base_url = 'http://localhost:80/salvataggio'
#base_url = 'https://europe-west8-progetto-delivery-452410.cloudfunctions.net/store'
with open('delivery.csv') as f:
    for l in f.readlines()[1:20]:
        ID, Delivery_ID, Delivery_age, Delivery_ratings, Restaruant_latitude, Restaruant_longitude, Delivery_latitude, Delivery_longitude, Type_of_order, Type_of_vehicle, Time_taken  = l.strip().split(
            ',')

        Dati = {
            'ID': ID,
            'Delivery_ID': Delivery_ID,
            'Delivery_age': Delivery_age,
            'Delivery_ratings': Delivery_ratings,
            'Restaurant_location': [Restaruant_latitude,Restaruant_longitude],
            'Delivery_location': [Delivery_latitude, Delivery_longitude],
            'Type_of_order': Type_of_order,
            'Type_of_vehicle': Type_of_vehicle,
            'Time_taken': Time_taken
        }


        r = requests.post(base_url, {'Data': json.dumps(Dati)})
        time.sleep(1)

        if r.status_code == 200:
            print(f"Successfully sent data for ID {Dati['ID']}")
        else:
            print(f"Failed to send data for ID {Dati['ID']} - Error: {r.text}")

print ('Done')
