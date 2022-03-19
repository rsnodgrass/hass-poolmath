# Pool Math for Home Assistant

![release_badge](https://img.shields.io/github/release/rsnodgrass/hass-poolmath.svg)
![release_date](https://img.shields.io/github/release-date/rsnodgrass/hass-poolmath.svg)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/DYks67r)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=WREP29UDAMB6G)  

Creates sensors for pools being managed with Trouble Free Pools's [Pool Math](https://www.troublefreepool.com/blog/poolmath/) apps including [Pool Math iOS](https://apps.apple.com/us/app/pool-math-by-troublefreepool/id1228819359) and [Pool Math Android](https://play.google.com/store/apps/details?id=com.troublefreepool.poolmath&hl=en_US). From the [Trouble Free Pool](https://troublefreepool.com/) website:

* Pool Math makes swimming pool care, maintenance and management easy by tracking chlorine, pH, alkalinity and other  levels to help calculate how much salt, bleach and other chemicals to add.
* Pool Math performs all the calculations you need to keep your chlorine, pH, calcium, alkalinity, and stabilizer levels balanced.
* [Trouble Free Pool](https://www.troublefreepool.com/) is a registered 501(c)3 non-profit who displays NO advertising on our site nor is our advice compromised by financial incentives.

#### Supported Pool Math Values

* pH
* Free Chlorine (FC)
* Combined Chlorine (CC)
* Total Alkalinity (TA)
* Calcium Hardness (CH)
* Cyanuric Acid (CYA)
* Salt
* Borates
* Calcite Saturation Index (CSI)
* Temperature

Note: this **requires a [Trouble Free Pool](https://www.troublefreepool.com/) Pool Math Premium subscription** to access your pool or spa's data from the Pool Math cloud service.

## Installation

Make sure [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is installed, then add the repository: `rsnodgrass/hass-poolmath`

### Configuration

Under Settings of the Pool Math iOS or Android application, find the Sharing section.  Turn this on, which allows anyone with access to the unique URL to be able to view data about your pool. Your pool's URL will be displayed, use that in the YAML configuration for the poolmath sensor.

```yaml
sensor:
  - platform: poolmath
    url: https://api.poolmathapp.com/share/7WPG8yL
```

NOTE: This updates the state from PoolMath every 15 minutes to keep from overwhelming their service, as the majority of Pool Math users update their data manual after testing rather than automated. The check interval can be changed in yaml config by adding a 'scan_interval' for the sensor.

### Example Lovelace UI

```yaml
entities:
  - entity: sensor.swimming_pool_fc
    name: Free Chlorine
  - entity: sensor.swimming_pool_ph
    name: pH
  - entity: sensor.swimming_pool_ta
    name: Total Alkalinity
  - entity: sensor.swimming_pool_cya
    name: CYA
  - entity: sensor.swimming_pool_ch
    name: Hardness
type: entities
title: Pool
show_header_toggle: false
```

![Lovelace Example](https://github.com/rsnodgrass/hass-poolmath/blob/master/img/example.png?raw=true)

Another single line Lovelace example using multiple-entity-row:

```yaml
entities:
  - entity: sensor.pool_ph
    type: 'custom:multiple-entity-row'
    name: Pool
    state_header: pH
    secondary_info: last-changed
    entities:
      - entity: sensor.pool_fc
        name: FC
      - entity: sensor.pool_cc
        name: CC
      - entity: sensor.pool_ta
        name: TA
  - entity: sensor.hot_tub_ph
    type: 'custom:multiple-entity-row'
    name: Hot Tub
    state_header: pH
    secondary_info: last-changed
    entities:
      - entity: sensor.hot_tub_fc
        name: FC
      - entity: sensor.hot_tub_cc
        name: CC
      - entity: sensor.hot_tub_ta
        name: TA
type: entities
```

![Lovelace Example](https://github.com/rsnodgrass/hass-poolmath/blob/master/img/example-multiple.png?raw=true)


## Support

### Community Support

* [How to use the Pool Math app?](https://www.troublefreepool.com/threads/how-to-use-the-pool-math-app.179282/)
* For issues with the Pool Math apps, see forums or contact [poolmath@troublefreepool.com](mailto:poolmath@troublefreepool.com)

### Feature Requests

* move all communication/interfaces to Pool Math into separate pypoolmath package that can be maintained separately
* on HA start, if the Pool Math cloud service is not available, no sensors are created (they get created later when service returns); ideas how to improve this:
  1. if Pool Math service is down, just create ALL sensors hardcoded in POOL_MATH_SENSOR_SETTINGS (or check to see if RestoreEnttiy has entries for those) ... this might be easiest, and could just be standard startup procedure
  2. update PoolMathServiceSensor to also use RestoreEntity and recreate all sensors that were saved in its state
* add Total Chlorine (TC) calculation
* make the HA yaml configuration for this a platform, rather than a sensor config...e.g.:

```yaml
poolmath:
  sources:
    - url: https://api.poolmathapp.com/share/tfp-168502
      name: "Swimming Pool"
    - url: https://api.poolmathapp.com/share/7WPG8yL
      name: "Spa"
```

### See Also

* [Trouble Free Pool Pool Math online calculator](https://www.troublefreepool.com/calc.html)
* [Pool Math apps](https://www.troublefreepool.com/blog/poolmath/) ([iOS](https://apps.apple.com/us/app/pool-math-by-troublefreepool/id1228819359), [Android](https://play.google.com/store/apps/details?id=com.troublefreepool.poolmath&hl=en_US))
* [ABC's of Pool Water Chemistry by Trouble Free Pool](https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/)
* [PookMath calculator](https://www.troublefreepool.com/calc.html)
* [PoolLab 1.0 Pool Chemical Tester with Bluetooth](https://www.amazon.com/Pool-Lab-1-0/dp/B0722ZD4G3?tag=rynoshark-20)
