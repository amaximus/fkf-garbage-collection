[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# FKF Budapest Garbage Collection custom component for Home Assistant

This custom component gathers garbage collection schedule from FKF Budapest Department of Public
for a configurable address.<p>

#### Installation
The easiest way to install it is through [HACS (Home Assistant Community Store)](https://custom-components.github.io/hacs/),
search for <i>FKF Budapest Garbage</i> in the Integrations.<br />

Sensors of this platform should be configured as per below information.

#### Configuration:
Define sensors with the following configuration parameters according to [FKF Hulladéknaptár](https://www.fkf.hu/hulladeknaptar/).<br />

---
| Name | Optional | `Default` | Description |
| :---- | :---- | :------- | :----------- |
| name | **N** | - | sensor of fkf_garbage_collection type |
| zipcode | **N** | - | ZIP code |
| publicplace | **N** | - | Name of public place |
| housenr | **N** | - | House number |
---

#### Example
```
platform: fkf_garbage_collection
name: 'fkf_my_schedule'
zipcode: '1013'
publicplace: 'Attila út'
housenr: '69'
```

#### Lovelace UI
There is a Lovelace custom card related to this component at [https://github.com/amaximus/fkf-garbage-collection-card](https://github.com/amaximus/fkf-garbage-collection-card).

#### Custom Lovelace card example:<br />
![Garbage Collection card example](fkf_alerted.png)
