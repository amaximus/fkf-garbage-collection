import asyncio
from datetime import timedelta
from datetime import datetime
import json
import logging
import lxml.html as lh
import re
import voluptuous as vol
import aiohttp

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform

from .calendar import EntitiesCalendarData
from .const import (
    DOMAIN,
    CALENDAR_NAME,
    CALENDAR_PLATFORM,
    SENSOR_PLATFORM,
)

REQUIREMENTS = [ ]

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by fkf.hu"
CONF_ZIPCODE = 'zipcode'
CONF_PUBLICPLACE = 'publicplace'
CONF_HOUSENR = 'housenr'
CONF_NAME = 'name'
CONF_OFFSETDAYS = 'offsetdays'
CONF_CALENDAR = 'calendar'
CONF_CALENDAR_LANG = 'calendar_lang'

DEFAULT_NAME = 'FKF Garbage'
DEFAULT_ICON = 'mdi:trash-can-outline'
DEFAULT_ICON_SELECTIVE = 'mdi:recycle'
DEFAULT_CONF_OFFSETDAYS = 0
DEFAULT_CONF_CALENDAR = 'false'
DEFAULT_CONF_CALENDAR_LANG = 'en'

#SCAN_INTERVAL = timedelta(hours=1)
SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIPCODE): cv.string,
    vol.Required(CONF_PUBLICPLACE): cv.string,
    vol.Required(CONF_HOUSENR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSETDAYS, default=DEFAULT_CONF_OFFSETDAYS): cv.positive_int,
    vol.Optional(CONF_CALENDAR, default=DEFAULT_CONF_CALENDAR): cv.boolean,
    vol.Optional(CONF_CALENDAR_LANG, default=DEFAULT_CONF_CALENDAR_LANG): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    zipcode = config.get(CONF_ZIPCODE)
    publicplace = config.get(CONF_PUBLICPLACE)
    housenr = config.get(CONF_HOUSENR)
    offsetdays = config.get(CONF_OFFSETDAYS)
    calendar = config.get(CONF_CALENDAR)
    calendar_lang = config.get(CONF_CALENDAR_LANG)

    session = async_get_clientsession(hass)

    async_add_devices(
        [FKFGarbageCollectionSensor(hass, name, zipcode, publicplace, housenr, offsetdays, calendar, calendar_lang)],update_before_add=True)

def dconverter(argument):
    switcher = {
      "Hétfő": "Monday",
      "Kedd": "Tuesday",
      "Szerda": "Wednesday",
      "Csütörtök": "Thursday",
      "Péntek": "Friday",
      "Szombat": "Saturday",
      "Vasárnap": "Sunday"
    }
    return switcher.get(argument)

def gconverter(argument):
    switcher = {
      "Szelektív": "selective",
      "Kommunális": "communal",
      'Szelektív Kommunális': "both",
      'Kommunális Szelektív': "both"
    }
    return switcher.get(argument)

async def async_get_fkfdata(self):
    payload_key = ["district","publicPlace","houseNumber"]
    october_par = ["ajax/publicPlaces","ajax/houseNumbers","ajax/calSearchResults"]
    october_hnd = ["onSelectDistricts","onSavePublicPlace","onSearch"]

    session = async_get_clientsession(self._hass)

    url = 'https://www.fkf.hu/'
    async with session.get(url) as response:
      r = await response.text()
      cookie = response.headers['Set-Cookie']

    url = 'https://www.fkf.hu/hulladeknaptar'

    payload_val = [self._zipcode, self._publicplace, self._housenr]

    for i in range(len(payload_key)):
       payload = {payload_key[i]: payload_val[i]}
       headers = {'X-OCTOBER-REQUEST-PARTIALS': october_par[i], \
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36', \
             'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', \
             'X-OCTOBER-REQUEST-HANDLER': october_hnd[i], \
             'Accept': '*/*', \
             'Sec-Fetch-Dest': 'empty', \
             'X-Requested-With': 'XMLHttpRequest', \
             'Cookie': cookie}
       async with session.post(url, data=payload, headers=headers) as response:
          fdata = await response.json()

    date_format = "%Y.%m.%d"
    today = datetime.today().strftime(date_format)

    s = fdata["ajax/calSearchResults"].replace("\n","").replace("\"","")
    s1 = re.sub("\s{2,}"," ",s)
    s = s1.replace("<div class=communal d-inline-block><i class=fas fa-trash fa-lg mr-2><","") \
          .replace("<div class=selective d-inline-block><i class=fas fa-trash fa-lg><","") \
          .replace("<i class=fas fa-trash fa-lg mr-2><","") \
          .replace("</div>","") \
          .replace("colspan=3><hr class=white m-0","") \
          .replace("/i>","")

    doc = lh.fromstring(s)
    tr_elements = doc.xpath('//tr')

    json_data_list = []
    if len(tr_elements) > 0:
      gday = tr_elements[0].xpath('//td[1]/text()')
      gdate = tr_elements[0].xpath('//td[2]/text()')
      garbage = tr_elements[0].xpath('//td[3]/text()')

      for i in range(len(garbage)-1):
        if garbage[i] and not garbage[i] == ' ':
          a = datetime.strptime(today, date_format)
          b = datetime.strptime(gdate[i], date_format)

          if (b - a).days - self._offsetdays >= 0:
            gtype = gconverter(garbage[i].strip())
            gdays = (b - a).days - self._offsetdays

            if gtype == "selective" and self._next_selective_days == None:
              self._next_selective_days = gdays
            if gtype == "communal" and self._next_communal_days == None:
              self._next_communal_days = gdays
            if gtype == "both" and self._next_selective_days == None:
              self._next_selective_days = gdays
              if self._next_communal_days == None:
                self._next_communal_days = gdays

            json_data = {"day": dconverter(gday[i]), \
                         "date": gdate[i], \
                         "garbage": gtype, \
                         "diff": gdays}
            json_data_list.append(json_data)
    else:
      _LOGGER.debug("Fetch info for %s/%s/%s: %s", self._zipcode, self._publicplace, self._housenr, s)

    return json_data_list

class FKFGarbageCollectionSensor(Entity):

    def __init__(self, hass, name, zipcode, publicplace, housenr, offsetdays, calendar, calendar_lang):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._zipcode = zipcode
        self._publicplace = "---".join(publicplace.rsplit(" ", 1))
        self._housenr = housenr
        self._state = None
        self._fkfdata = []
        self._current = "current"
        self._offsetdays = offsetdays
        self._icon = DEFAULT_ICON
        self._next_communal_days = None
        self._next_selective_days = None
        self._calendar = calendar
        self._calendar_lang = calendar_lang

    async def async_added_to_hass(self):
        """When sensor is added to hassio, add it to calendar."""
        await super().async_added_to_hass()
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if SENSOR_PLATFORM not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][SENSOR_PLATFORM] = {}
        self.hass.data[DOMAIN][SENSOR_PLATFORM][self.entity_id] = self

        if self._calendar:
            if CALENDAR_PLATFORM not in self.hass.data[DOMAIN]:
                 self.hass.data[DOMAIN][CALENDAR_PLATFORM] = EntitiesCalendarData(self.hass)
                 _LOGGER.debug("Creating fkfgarbage_collection calendar " + self._name)
                 self.hass.async_create_task(
                      async_load_platform(
                          self.hass,
                          CALENDAR_PLATFORM,
                          DOMAIN,
                          {"name": CALENDAR_NAME},
                          {"name": CALENDAR_NAME},
                      )
                 )
            self.hass.data[DOMAIN][CALENDAR_PLATFORM].add_entity(self.entity_id)

    async def async_will_remove_from_hass(self):
        """When sensor is added to hassio, remove it."""
        await super().async_will_remove_from_hass()
        del self.hass.data[DOMAIN][SENSOR_PLATFORM][self.entity_id]
        self.hass.data[DOMAIN][CALENDAR_PLATFORM].remove_entity(self.entity_id)

    @property
    def device_state_attributes(self):
        attr = {}

        attr["items"] = len(self._fkfdata)
        attr["current"] = self._current
        if attr["items"] != 0:
          i = 0
          while i < len(self._fkfdata):
            attr['in' + str(i)] = self._fkfdata[i]['diff']
            attr['day' + str(i)] = self._fkfdata[i]['day']
            attr['date' + str(i)] = self._fkfdata[i]['date']
            attr['garbage' + str(i)] = self._fkfdata[i]['garbage']
            i += 1

        attr["next_communal_days"] = self._next_communal_days
        attr["next_selective_days"] = self._next_selective_days
        attr["calendar_lang"] = self._calendar_lang

        attr["provider"] = CONF_ATTRIBUTION
        return attr

    def __repr__(self):
        """Return main sensor parameters."""
        return (
            f"FKFGarbagecollection[ name: {self._name}, "
            f"entity_id: {self.entity_id}, "
            f"state: {self.state}\n"
            f"config: {self.config}]"
        )

    @asyncio.coroutine
    async def async_update(self):
        self._next_communal_days = None
        self._next_selective_days = None

        fkfdata = await async_get_fkfdata(self)

        if len(fkfdata) != 0:
           self._fkfdata = fkfdata
           self._state = self._fkfdata[0]['diff']
           self._current = "current"
        else:
           self._current = "not_current"
        return self._state

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if self._fkfdata[0]['garbage'] == "communal":
            return DEFAULT_ICON
        else:
            return DEFAULT_ICON_SELECTIVE
