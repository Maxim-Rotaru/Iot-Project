let temperatureGauge;
let humidityGauge;
let luminosityGauge;
let hasEmailSent = false;
  
window.onload = () => {
    // Initialize everything first
    initializeGauges();
    autoPopulateForm(); 
    setInterval(autoPopulateForm, 3000); 


    document.getElementById('toggle-switch').addEventListener('change', function() {
        let newState = this.checked ? 'ON' : 'OFF';
        fetch(`/toggle_led/${newState}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => updateLED(data.led_status));
    });

    setInterval(() => {
        fetchData(); 
        fetchLightData();
        },
        1000);
    updateLED("{{ led_status }}");
    updateFan("{{ fan_status }}");
    };

function initializeGauges() {
    temperatureGauge = new JustGage({
        id: "temperature-gauge",
        value: -1,
        decimals: 1,
        min: 15,
        max: 30,
        title: "Temperature",
        symbol: "°C",
        gaugeWidthScale: 0.5,
        pointer: true,
    });

    humidityGauge = new JustGage({
        id: "humidity-gauge",
        donut: true,
        value: -1,
        decimals: 1,
        min: 0,
        max: 100,
        title: "Humidity",
        symbol: "%",
        gaugeWidthScale: 0.5,
        levelColors: ["#b5e8f5", "#2e98b3", "#0000ff"],
    });

    luminosityGauge = new JustGage({
       id: "luminosity-gauge",
       value: -1,
       min: 0,
       max: 5000,
       reverse: true,
       title: "Luminosity",
       gaugeWidthScale: 0.5,
       levelColors: ["#f7f697","#d1cfb6", "#2a2a2a"],
    });
}

function fetchData() {
    fetch('/sensor_data')
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            if (data.temperature || data.temperature === 0) {
                // Update the gauges with values
                temperatureGauge.refresh(data.temperature);

                updateFan("{{ fan_status }}", "{{ fan_switch_requested }}");
            }
            if (data.humidity || data.humidity === 0) {
                // Update the gauges with values
                humidityGauge.refresh(data.humidity);
            }
        })
        .catch(error => console.error('Error fetching sensor data:', error));
}

function fetchLightData() {
    fetch('/light_data')
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            if (data.luminosity || data.luminosity === 0) {
                // Update the gauges with values
                luminosityGauge.refresh(data.luminosity);
            }
        })
        .catch(error => console.error('Error fetching sensor data:', error));
}

function updateLED(ledStatus) {
    // Defining the variables
    const lightImage = document.getElementById('light-icon');
    const toggleSwitch = document.getElementById('toggle-switch');

    // Assigning the variables and displaying on the page
    toggleSwitch.checked = (ledStatus === 'ON');
    lightImage.src = (ledStatus === 'ON') ? ('/static/images/lit.png') : ('/static/images/dark.png');
    // If not received yet, don't want to display "{{ led_status }}"
    if (ledStatus === "{{ led_status }}") {
        document.getElementById('led-status').textContent = "LED Status: OFF";
    } else {
        document.getElementById('led-status').textContent = "LED Status: " + ledStatus;
    }
    lightImage.className = (ledStatus === 'ON') ? 'lit' : 'dark';
}


function updateFan(fanStatus, fanSwitchRequested) {
    const fanIcon = document.getElementById('fan-icon');

    fanIcon.src = (fanStatus === 'ON' && fanSwitchRequested) ? ('/static/images/FanOn.png') : ('/static/images/FanOff.png');
    // If not received yet, don't want to display "{{ fan_status }}"
    if (fanStatus === "{{ fan_status }}") {
        document.getElementById('fan-status').textContent = "Fan Status: OFF";
    } else {
        document.getElementById('fan-status').textContent = "Fan Status: " + fanStatus;
    }
}

function checkEmailNotification() {
    fetch('/check_email_notification')
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                // If there's a notification, show a popup
                alert(data.message);
            }
        })
        .catch(error => console.error('Error checking email notification:', error));
}
let currentRfid = localStorage.getItem('currentRfid') || "";

function autoPopulateForm() {
    fetch('/fetch_user', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({}) // Server infers the scanned RFID
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.warn('No user data:', data.error);
            return;
        }

        if (currentRfid !== data.rfid_tag) {
            currentRfid = data.rfid_tag;
            localStorage.setItem('currentRfid', currentRfid);
        }

        // Update the User Info section in your new HTML
        document.getElementById('username').textContent = data.username ? `Hello, ${data.username}` : 'Hello';
        document.getElementById('rfid_display').textContent = `RFID Tag: ${data.rfid_tag || ''}`;
        document.getElementById('email').textContent = `Email: ${data.email || ''}`;

    })
    .catch(error => {
        console.error('Error fetching RFID/user data:', error);
    });
}
