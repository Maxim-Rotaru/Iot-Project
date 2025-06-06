import RPi.GPIO as GPIO
from gpiozero import DigitalOutputDevice
from flask import Flask, render_template, request, jsonify
import atexit
import paho.mqtt.client as mqtt
from Freenove_DHT import DHT
import smtplib
from email.mime.text import MIMEText
from threading import Thread
import time
import ssl
from email.message import EmailMessage
import imaplib
import email
from email.header import decode_header
from email.header import decode_header
import sqlite3
from bluetooth_helper import BluetoothHelper # Importing hte bluetooth file 

# Define pin assignments
LED_PIN = 12    # LED control pin
FAN_POWER_PIN = 22    # Fan (DC motor) control pin
FAN_PIN = 17    # Fan (DC motor) control pin
DHT_PIN = 26     # DHT-11 sensor pin

GPIO.setwarnings(False) #disable warnings
# Set up GPIO for LED and Fan
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.setup(FAN_POWER_PIN, GPIO.OUT)

# Turn off LED and fan by default

GPIO.output(LED_PIN, GPIO.LOW)
GPIO.output(FAN_PIN, GPIO.LOW)
GPIO.output(FAN_POWER_PIN, GPIO.HIGH)


# Initialize DHT sensor
dht_sensor = DHT(DHT_PIN)


# MQTT configuration
MQTT_BROKER = '192.168.3.131'
#MQTT_BROKER = 'localhost' # in case normal broker breaks
MQTT_TOPIC_LED = 'home/led'
MQTT_TOPIC_FAN = 'home/fan'
MQTT_TOPIC_LIGHT = 'home/light'
MQTT_TOPIC_RFID = 'home/rfid'
# Fan / light states 
led_state = 'OFF'
fan_state = 'OFF'
fan_switch_on = False
fan_switch_off = False # used to tell the frontend when the temperature drops back down
fan_email_sent = False
# Light Variables
light_intensity = 0
light_email_sent = False

current_user = {}  # Global variable to store the current user's data !!!
current_rfid = '83adf703'; 
bt_helper = BluetoothHelper()
bluetooth_devices = bt_helper.get_bluetooth_devices()

#initialize db method called in render html !!!
def init_db():
    conn = sqlite3.connect('smart_home.db')
    cursor = conn.cursor()
    
    # Create the users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            rfid_tag TEXT UNIQUE NOT NULL,
            temperature_threshold INTEGER DEFAULT 24,
            light_intensity_threshold INTEGER DEFAULT 400
        )
    ''')
    
    # Insert default data
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, rfid_tag, temperature_threshold, light_intensity_threshold)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Karlito', 'karlalvarado666@gmail.com', 'xxxxxxxx', 25, 450))

    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, rfid_tag, temperature_threshold, light_intensity_threshold)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Maxim1', 'maximrotaru16@gmail.com', '83adf703', 24, 400))
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, rfid_tag, temperature_threshold, light_intensity_threshold)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Maxim2', 'lemonboysomething@gmail.com', 'a43a1051', 23, 500))
    
    conn.commit()
    conn.close()


# Retrieve user data !!!
def get_user(rfid_tag):
    global fan_email_sent
    global light_email_sent
    conn = sqlite3.connect('smart_home.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE rfid_tag = ?', (rfid_tag,))
    user = cursor.fetchone()
    fan_email_sent = False
    light_email_sent = False
    conn.close()
    return user 


def send_email(temperature):
    global fan_email_sent
    current_user = get_user(current_rfid)
    if not fan_email_sent:
        msg = MIMEText(f"The current temperature is {temperature}°C. Would you like to turn on the fan?")
        msg['Subject'] = 'Temperature Alert'
        msg['From'] = 'whatisiot1@gmail.com'
        msg['To'] = current_user[2]

        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login('whatisiot1@gmail.com', 'ayvi plyw mqzd vrtz')
            server.sendmail(msg['From'], [msg['To']], msg.as_string())
        fan_email_sent = True
        print('Email sent')

def check_email_responses():
    global fan_switch_on
    global fan_state
    while True:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(username, imap_password)
            mail.select("inbox")

            # Search for all messages in the inbox
            status, messages = mail.search(None, 'ALL')
            email_ids = messages[0].split()

            # Fetch and process each email
            for email_id in email_ids:
                # Decode email_id, since imaplib returns a byte string
                email_id = email_id.decode()

                res, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        body = None

                        # If the message is multipart, find the plain-text part
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True).decode()  # Decode the body
                                    body.lower() # converts to lowercase
                                    break
                        else:
                            # If not multipart, get the payload directly
                            body = msg.get_payload(decode=True).decode()
                            body.lower() # converts to lowercase

                        if body:

                            # Check for "Yes" in the email body
                            if "yes" in body:
                                print("Yes detected in response, activating FAN")
                                mail.store(email_id, '+FLAGS', '\\Deleted')
                                mail.expunge()
                                GPIO.output(FAN_PIN, GPIO.HIGH)
                                # These two variables should always be set together
                                fan_switch_on = True
                                fan_state = 'ON'

            mail.logout()
            time.sleep(10)

        except Exception as e:
            print(f"Error checking emails: {e}")

def send_light_email():
    global light_email_sent
    global current_user
    current_user = get_user(current_rfid)
    if not light_email_sent and 'email' in current_user:
        msg = MIMEText(f"Dark room detected. LED Light has been activated.")
        msg['Subject'] = 'LED Enabled'
        msg['From'] = 'whatisiot1@gmail.com'
        msg['To'] = current_user[2]  # send email to the current user
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login('whatisiot1@gmail.com', 'ayvi plyw mqzd vrtz')
                server.sendmail(msg['From'], [msg['To']], msg.as_string())
            print(f"Light activation email sent to {current_user['email']}")
            light_email_sent = True
        except Exception as e:
            print(f"Failed to send email: {e}")


# -------------------------------------------------------------------------------------------------------------------------->


# MQTT setup
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, 1883, 60)
mqtt_client.loop_start()

# Email password & port
port = 465
app_specific_password = "ayvi plyw mqzd vrtz"

# Email configuration for checking responses
username = "whatisiot1@gmail.com"
imap_password = "ayvi plyw mqzd vrtz"

# Flask setup
app = Flask(__name__)


#Method when MQTT receive data from subscribed topic !!!
def on_message(client, userdata, msg):
    global light_intensity, light_email_sent, led_state, fan_state, fan_switch_on, fan_email_sent, current_rfid
    global current_user
    current_user = get_user(current_rfid)
    if msg.topic == MQTT_TOPIC_LIGHT:
        try:
            light_intensity = int(msg.payload.decode())  # Decode and store the light intensity value
            print(f"Received light intensity: {light_intensity}")
            if light_intensity > current_user[5] and not light_email_sent:
                led_state = 'ON'
                GPIO.output(LED_PIN, GPIO.HIGH)
                send_light_email()
                light_email_sent = True
            elif light_intensity <= current_user[5]:
                led_state = 'OFF'
                GPIO.output(LED_PIN, GPIO.LOW)
                light_email_sent = False
        except ValueError:
            print(f"Invalid light intensity value received: {msg.payload.decode()}")
    
    elif msg.topic == MQTT_TOPIC_RFID: # hi !!!
        try:
            rfid = msg.payload.decode()
            print(f"RFID Detected: {rfid}")
            current_rfid = rfid
            # Fetch user details from the database
            user = get_user(rfid)
        
            if user:
               
                current_user = {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'rid_tag': user[3],
                    'temperature_threshold': user[4],
                    'light_intensity_threshold': user[5]
                }
            
                print(f"Switched to preferences for user: {current_user['username']}")
                
                # Notify the user via email
                notification_msg = f"""
                Hello {current_user['username']},
    
                Your preferences have been successfully activated at {time}:
                - Temperature Threshold: {current_user['temperature_threshold']}°C
                - Light Intensity Threshold: {current_user['light_intensity_threshold']} lumens
    
                Thank you,
                Beep boop smart IoT system
                """
                send_email_to_user(current_user['email'], "Preferences Activated", notification_msg)
            else:
                print("No user found with this RFID tag.")
        except ValueError:
            print(f"Invalid RFID Value: {msg.payload.decode()}")



def send_email_to_user(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = 'whatisiot1@gmail.com'
        msg['To'] = to_email

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login('whatisiot1@gmail.com', 'ayvi plyw mqzd vrtz')
            server.sendmail(msg['From'], [to_email], msg.as_string())
        
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")




def read_dht_sensor():
    chk = dht_sensor.readDHT11()
    if chk == 0:  # 0 indicates successful read
        humidity = dht_sensor.getHumidity()
        temperature = dht_sensor.getTemperature()
        return humidity, temperature
    else:
        return None, None


# Function to monitor temperature and control fan
def monitor_temperature():
    global fan_state
    global fan_switch_off
    global fan_email_sent
    global current_user
    current_user = get_user(current_rfid)
    while True:
        humidity, temperature = read_dht_sensor()
        if temperature is not None:
            print(f"Temperature: {temperature}°C, Humidity: {humidity}%")
            if temperature >= current_user[4] and fan_state == 'OFF':
                if fan_email_sent == False:
                    send_email(temperature)
                    fan_email_sent = True
            elif temperature < current_user[4] and fan_state == 'ON':
                fan_state = 'OFF'
                fan_switch_off = True # setting this so frontend knowns to turn fan off
                GPIO.output(FAN_PIN, GPIO.LOW)
        time.sleep(3)

# Start monitoring thread
Thread(target=monitor_temperature, daemon=True).start()
# Check email response thread
Thread(target=check_email_responses, daemon=True).start()
# Thread to do bluetooth
Thread(target=start_bluetooth_scan, daemon=True).start()

mqtt_client.on_message = on_message  # Attach the handler 
mqtt_client.subscribe(MQTT_TOPIC_LIGHT)  # Subscribe to the light intensity topic
mqtt_client.subscribe(MQTT_TOPIC_RFID)   # Subscribe to RFID Topic !!!

# Route to render the dashboard
@app.before_first_request
def setup():
    # Initialize the database
    init_db()
    conn = sqlite3.connect('smart_home.db')
    cursor = conn.cursor()

@app.route('/')
def index():
    return render_template(
        'dashboard.html', 
        led_status=led_state,
        light_email_sent=light_email_sent,
        fan_status=fan_state,
        fan_switch_on=fan_switch_on,
        fan_switch_off=fan_switch_off,
        fan_email_sent=fan_email_sent,
        devices=bluetooth_devices,
        current_user=current_user  # Pass the current_user object to the template
    )
# Route to toggle LED via MQTT
@app.route('/toggle_led/<state>', methods=['POST'])
def toggle_led(state):
    global led_state
    led_state = state
    print(f"LED state set to: {led_state}") # Debugging purposes
    mqtt_client.publish(MQTT_TOPIC_LED, led_state)
    GPIO.output(LED_PIN, GPIO.HIGH if led_state == 'ON' else GPIO.LOW)
    return jsonify({'led_status': led_state}), 200

# Route to control fan via MQTT
@app.route('/toggle_fan/<state>', methods=['POST'])
def toggle_fan(state):
    global fan_state
    fan_state = state
    print(f"Fan state set to: {fan_state}") # Debugging purposes
    mqtt_client.publish(MQTT_TOPIC_FAN, fan_state)
    GPIO.output(FAN_PIN, GPIO.HIGH if fan_state == 'ON' else GPIO.LOW)
    return jsonify({'fan_status': fan_state}), 200

# Handle app exit to ensure GPIO is cleaned up
def on_exit():
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.output(FAN_PIN, GPIO.LOW)
    GPIO.cleanup()
    mqtt_client.publish(MQTT_TOPIC_LED, 'OFF')
    mqtt_client.publish(MQTT_TOPIC_FAN, 'OFF')
    mqtt_client.publish(MQTT_TOPIC_RFID, 'OFF')

@app.route('/sensor_data')
def sensor_data():
    humidity, temperature = read_dht_sensor()  # Call your DHT sensor function
    if humidity is not None and temperature is not None:
        return jsonify({'temperature': temperature, 'humidity': humidity})
    else:
        return jsonify({'error': 'Could not retrieve sensor data'}), 500
    
@app.route('/light_data')
def light_data():
    if light_intensity is not None:
        return jsonify({'luminosity': light_intensity})
    else:
        return jsonify({'error': 'Could not retrieve sensor data'}), 500

#trying some stuff here -max
@app.route('/get_states')
def get_states():
    if led_state is not None and fan_state is not None and fan_switch_on is not None and fan_switch_off is not None and fan_email_sent is not None:
        return jsonify({'ledStatus': led_state, 'fanStatus': fan_state, 'fanSwitchOn': fan_switch_on, 'fanSwitchOff': fan_switch_off, 'fanEmailSent': fan_email_sent})
    else:
        return jsonify({'error': 'Could not retrieve states'}), 500

# Checking the email has been sent for the light
@app.route('/check_email_notification')
def check_email_notification():
    global light_email_sent
    if light_email_sent:
        # Reset the notification flag to avoid repeated alerts
        light_email_sent = False
        return jsonify({'message': 'Light Notification Has Been Sent.'}), 200
    else:
        return jsonify({'message': None}), 200

#------------------------------------------------------------------------------->

# Auto filling the form's information !!!
@app.route('/fetch_user', methods=['POST'])
def fetch_user():
    global current_user
    
    ## Line that populates currently 
    rfid_tag = request.json.get('rfid_tag')

    if current_rfid:
        rfid_tag = current_rfid
    
    if rfid_tag:
        current_user = get_user(rfid_tag)
    else:
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY id ASC LIMIT 1')
        currrent_user = cursor.fetchone()
        conn.close()
    
    if current_user:
        return jsonify({
            'id': current_user[0],
            'username': current_user[1],
            'email': current_user[2],
            'rfid_tag': current_user[3],
            'temperature_threshold': current_user[4],  
            'lighting_intensity_threshold': current_user[5],  
        })
    else:
        return jsonify({'error': 'No users found in the database'}), 404

# Flask Route to serve Bluetooth devices
@app.route('/bluetooth_devices')
def bluetooth_devices_list():
    return jsonify(bluetooth_devices)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)