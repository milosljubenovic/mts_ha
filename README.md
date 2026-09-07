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

1. In HACS, go to **Integrations** → **⋮** → **Custom repositories**
2. Add `https://github.com/milosljubenovic/mts_ha` (category: **Integration**)
3. Open **MTS RS** in HACS and click **Download**
4. If HACS shows a version selector, choose the latest **release** (for example `v1.0.2`), not a commit hash
5. Restart Home Assistant
6. Go to **Settings → Devices & services → Add integration**
7. Search for **MTS RS**
8. Login with your Moj mts username and password
9. Select the phone numbers you want to track

### HACS download failed with 404?

HACS sometimes tries to download a commit hash as a branch, which GitHub rejects. To fix it:

1. In HACS, remove **MTS RS** if it is already listed
2. Remove the custom repository entry, then add it again
3. Download again and pick the latest **release** version from the dropdown
4. If it still fails, use [manual installation](#manual-installation) below

## Manual installation

Copy `custom_components/mts_rs` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Options

After setup, open the integration options to change the update interval. Minimum is 60 seconds, maximum is 86400 seconds.

## Notes

- Use your Moj mts **username**, not your email address, unless your account uses email for login
- This integration uses the same unofficial API as the Moj mts web portal
