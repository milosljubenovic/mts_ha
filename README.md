# MTS RS Home Assistant Integration

Home Assistant custom integration for tracking Moj mts prepaid internet quota, active packages, and balance.

## Features

- Config Flow setup with username/password login
- Automatic discovery of phone numbers on your account
- Track multiple MSISDNs from one account
- Session persistence across Home Assistant restarts
- Reuses an active session when possible, otherwise logs in again
- Configurable polling interval (default: 3600 seconds)

## Sensors per phone number

- Internet remaining (GB)
- Balance (RSD)
- Active package name
- Package valid until
- Quota valid until

Each sensor also exposes detailed attributes such as formatted balance, all active packages, and bonus quota entries.

## HACS installation

1. Add this repository as a custom HACS repository
2. Install **MTS RS** from HACS integrations
3. Restart Home Assistant
4. Go to **Settings → Devices & services → Add integration**
5. Search for **MTS RS**
6. Login with your Moj mts username and password
7. Select the phone numbers you want to track

## Manual installation

Copy `custom_components/mts_rs` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Options

After setup, open the integration options to change the update interval. Minimum is 60 seconds, maximum is 86400 seconds.

## Notes

- Use your Moj mts **username**, not your email address, unless your account uses email for login
- This integration uses the same unofficial API as the Moj mts web portal
