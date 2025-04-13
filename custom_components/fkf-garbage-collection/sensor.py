from datetime import timedelta
from datetime import datetime
import aiohttp
import asyncio
import json
import logging
import lxml.html as lh
import re
import time
import voluptuous as vol

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
    URL,
)

REQUIREMENTS = [ ]

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by " + URL
CONF_ZIPCODE = 'zipcode'
CONF_PUBLICPLACE = 'publicplace'
CONF_HOUSENR = 'housenr'
CONF_NAME = 'name'
CONF_OFFSETDAYS = 'offsetdays'
CONF_CALENDAR = 'calendar'
CONF_CALENDAR_LANG = 'calendar_lang'
CONF_GREEN = 'green'
CONF_GREENCOLOR = 'greencolor'
CONF_CITY = 'city'
CONF_SSL = "ssl"

DEFAULT_NAME = 'FKF Garbage'
DEFAULT_ICON = 'mdi:trash-can-outline'
DEFAULT_ICON_GREEN = 'mdi:leaf'
DEFAULT_ICON_SELECTIVE = 'mdi:recycle'
DEFAULT_CONF_CALENDAR = 'false'
DEFAULT_CONF_CALENDAR_LANG = 'en'
DEFAULT_CONF_CITY = 'Budapest'
DEFAULT_CONF_GREEN = 'false'
DEFAULT_CONF_GREENCOLOR = ''
DEFAULT_CONF_HOUSENR = '1'
DEFAULT_CONF_OFFSETDAYS = 0
DEFAULT_CONF_SSL = False

HTTP_TIMEOUT = 60 # secs
MAX_RETRIES = 3
SCAN_INTERVAL = timedelta(hours=1)
ZIPCODE_BUDAORS = '2040'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIPCODE): cv.string,
    vol.Required(CONF_PUBLICPLACE): cv.string,
    vol.Optional(CONF_HOUSENR, default=DEFAULT_CONF_HOUSENR) : cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSETDAYS, default=DEFAULT_CONF_OFFSETDAYS): cv.positive_int,
    vol.Optional(CONF_CALENDAR, default=DEFAULT_CONF_CALENDAR): cv.boolean,
    vol.Optional(CONF_CALENDAR_LANG, default=DEFAULT_CONF_CALENDAR_LANG): cv.string,
    vol.Optional(CONF_GREEN, default=DEFAULT_CONF_GREEN): cv.boolean,
    vol.Optional(CONF_GREENCOLOR, default=DEFAULT_CONF_GREENCOLOR): cv.string,
    vol.Optional(CONF_CITY, default=DEFAULT_CONF_CITY): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_CONF_SSL): cv.boolean,
})

MAR1 = 60
DEC3 = 337

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    zipcode = config.get(CONF_ZIPCODE)
    publicplace = config.get(CONF_PUBLICPLACE)
    housenr = config.get(CONF_HOUSENR)
    offsetdays = config.get(CONF_OFFSETDAYS)
    calendar = config.get(CONF_CALENDAR)
    calendar_lang = config.get(CONF_CALENDAR_LANG)
    green = config.get(CONF_GREEN)
    greencolor = config.get(CONF_GREENCOLOR)
    city = config.get(CONF_CITY)
    ssl = config.get(CONF_SSL)

    async_add_devices(
        [FKFGarbageCollectionSensor(hass, name, zipcode, publicplace, housenr, offsetdays, calendar, calendar_lang, green, greencolor, ssl)],update_before_add=True)

def cconverter(argument):
    switcher = {
     '1730799272633': 'lila',
     '1730799060208': 'lila',
     '1730798058029': 'lila',
     '1730798863644': 'lila',
     '1730798333275': 'lila',
     '1730797853938': 'lila',
     '1730725941615': 'lila',
     '1730798057927': 'sarga',
     '1730799060147': 'sarga',
     '1730798863545': 'sarga',
     '1730798700732': 'sarga',
     '1730798333170': 'sarga',
     '1730797852879': 'sarga',
     '1730797561410': 'sarga',
     '1730727535462': 'sarga',
     '1730726485559': 'sarga',
     '1730726265826': 'sarga',
     '1730725940106': 'sarga',
     '1730725715050': 'sarga',
     '1730798058079': 'narancs',
     '1730799060260': 'narancs',
     '1730799406551': 'narancs',
     '1730798863693': 'narancs',
     '1730798333341': 'narancs',
     '1730797852923': 'narancs',
     '1730797561506': 'narancs',
     '1730727534434': 'narancs',
     '1730726824494': 'narancs',
     '1730726485505': 'narancs',
     '1730725941738': 'narancs',
     '1730370882590': 'narancs',
     '1730798058121': 'kek',
     '1730799406551': 'kek',
     '1730799060306': 'kek',
     '1730798863593': 'kek',
     '1730798700841': 'kek',
     '1730798333398': 'kek',
     '1730797561464': 'kek',
     '1730727534484': 'kek',
     '1730727235202': 'kek',
     '1730727043249': 'kek',
     '1730726486784': 'kek',
     '1730799406597': 'rozsaszin',
     '1730798057986': 'rozsaszin',
     '1730798700784': 'rozsaszin',
     '1730798333227': 'rozsaszin',
     '1730797853826': 'rozsaszin',
     '1730727534385': 'rozsaszin',
     '1730725940148': 'rozsaszin',
     '1730725197235': 'rozsaszin'
    }
    return switcher.get(argument)

def dconverter(argument):
    switcher = {
      'Csütörtök': 'Thursday',
      'Hétfő': 'Monday',
      'Kedd': 'Tuesday',
      'Péntek': 'Friday',
      'Szerda': 'Wednesday',
      'Szombat': 'Saturday',
      'Vasárnap': 'Sunday'
    }
    return switcher.get(argument)

def gconverter(argument):
    switcher = {
      "Szelektív": "selective",
      "Kommunális": "communal",
      'Zöld': "green",
      'Szelektív Kommunális': "communal_selective",
      'Kommunális Szelektív': "communal_selective",
      'Kommunális Zöld': "communal_green",
      'Zöld Kommunális': "communal_green",
      'Szelektív Zöld': "selective_green",
      'Zöld Szelektív': "selective_green",
      'Kommunális Szelektív Zöld': "communal_selective_green",
      'Kommunális Zöld Szelektív': "communal_selective_green",
      'Szelektív Kommunális Zöld': "communal_selective_green",
      'Szelektív Zöld Kommunális': "communal_selective_green",
      'Zöld Kommunális Szelektív': "communal_selective_green",
      'Zöld Szelektív Kommunális': "communal_selective_green"
    }
    return switcher.get(argument)

def _getRomanDistrictFromZip(argument):
    district10 = int(argument[1:3])
    districtR = _int_to_Roman(district10)
    return districtR.lower()

def _int_to_Roman(num):
    val = [
         1000, 900, 500, 400,
         100, 90, 50, 40,
         10, 9, 5, 4,
         1
         ]
    syb = [
        "M", "CM", "D", "CD",
        "C", "XC", "L", "XL",
        "X", "IX", "V", "IV",
        "I"
        ]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syb[i]
            num -= val[i]
        i += 1
    return roman_num

def _sleep(secs):
    time.sleep(secs)

async def async_get_fkfdata(self):
    weekdays = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    green_dayEN = None
    green_not_added = True
    s = ""
    s1 = ""
    s2 = ""
    fdata = {}
    tr_elements = []
    cookie = ""
    _session = async_get_clientsession(self._hass, self._ssl)

    date_format = "%Y.%m.%d"
    today = datetime.today().strftime(date_format)
    if int(datetime.today().strftime('%j')) < MAR1 or int(datetime.today().strftime('%j')) > DEC3:
      self._green = False
      self._green_green_days = None

    if self._green and self._zipcode != ZIPCODE_BUDAORS:
        url = 'https://' + URL + '/kerti-zoldhulladek-korzetek-' + _getRomanDistrictFromZip(self._zipcode) + '-kerulet'
        for i in range(MAX_RETRIES):
          try:
              async with _session.get(url, timeout=HTTP_TIMEOUT) as response:
                  r = await response.text()
                  s = r.replace("\r","").split("\n")
              if not response.status // 100 == 2:
                  _LOGGER.debug("Fetch attempt " + str(i+1) + ": unexpected response " + str(response.status))
                  await self._hass.async_add_executor_job(_sleep, 10)
              else:
                  break

          except Exception as err:
              _LOGGER.debug("Fetch attempt " + str(i+1) + " failed for green schedule " + url)
              _LOGGER.error(f'error: {err} of type: {type(err)}')
              s = ""
              self._green = False
              self._green_green_days = None
              await self._hass.async_add_executor_job(_sleep, 10)

        CLEANHTML = re.compile('<.*?>')

        for ind,line in enumerate(s):
          matchre = re.compile(r'<strong>[A-ZÁÉÖŐÜ]+\&nbsp\;</strong>')
          m = re.search(matchre,line)
          if m != None:
            s2 = re.sub(CLEANHTML,'',line.replace("&nbsp;","").replace("\t","")) \
                 .lower().capitalize()
            _LOGGER.debug("Green: " + s2)
            break

        if self._green:
          today_wday = datetime.today().weekday()
          green_dayEN = dconverter(s2)
          if green_dayEN != None:
            green_day_diff = (weekdays.index(green_dayEN) + 7 - today_wday) % 7 - self._offsetdays
            if green_day_diff < 0:
              green_day_diff += 7
            green_date = datetime.strptime(today, date_format) + timedelta(days=green_day_diff + self._offsetdays)
            if self._next_green_days == None:
              self._next_green_days = green_day_diff

    url = 'https://' + URL + '/'
    try:
        async with _session.get(url, timeout=HTTP_TIMEOUT) as response:
            r = await response.text()
            cookie = response.headers['Set-Cookie']
    except (aiohttp.ContentTypeError, aiohttp.ServerDisconnectedError, asyncio.TimeoutError):
        _LOGGER.debug("Connection error to " + URL)

    if self._zipcode == ZIPCODE_BUDAORS:
      url = 'https://' + URL + '/hulladeknaptar-budaors'
      payload_val = [self._publicplace]
      payload_key = ["publicPlace"]
      october_par = ["ajax/budaorsResults"]
      october_hnd = ["onSearch"]
    else:
      url = 'https://' + URL + '/hulladeknaptar'
      payload_val = [self._zipcode, self._publicplace, self._housenr]
      payload_key = ["district","publicPlace","houseNumber"]
      october_par = ["ajax/publicPlaces","ajax/houseNumbers","ajax/calSearchResults"]
      october_hnd = ["onSelectDistricts","onSavePublicPlace","onSearch"]

    if len(cookie) != 0:
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
            try:
                async with _session.post(url, data=payload, headers=headers, timeout=HTTP_TIMEOUT) as response:
                    fdata = await response.json()
            except (aiohttp.ContentTypeError, aiohttp.ServerDisconnectedError, asyncio.TimeoutError):
                _LOGGER.debug("Connection error to fetch data from " + url)
                break

    if 'ajax/calSearchResults' in fdata:
      s1 = fdata["ajax/calSearchResults"]
    if 'ajax/budaorsResults' in fdata:
      s1 = fdata["ajax/budaorsResults"]

    if len(s1) > 0:
      s = s1.replace("\n","").replace("\"","")
      s1 = re.sub(r'\s{2,}',' ',s)
      s = s1.replace("<div class=communal d-inline-block><i class=fas fa-trash fa-lg mr-2><","") \
            .replace("<div class=selective d-inline-block><i class=fas fa-trash fa-lg><","") \
            .replace("<i class=fas fa-trash fa-lg mr-2><","") \
            .replace("<i class=fab fa-pagelines fa-lg mr-2 style=color:green;><","") \
            .replace("<div class=communal d-inline-block>","") \
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
            if gdays is None:
              gdays = -1
            _LOGGER.debug(self._publicplace + ": " + str(gdays) + ": " + gtype)

            if "selective" in gtype and self._next_selective_days == None:
              self._next_selective_days = gdays

            if "communal" in gtype and self._next_communal_days == None:
              self._next_communal_days = gdays

            if "green" in gtype and self._next_green_days == None:
              self._next_green_days = gdays

            if self._green and self._next_green_days != None and self._zipcode != ZIPCODE_BUDAORS:
                if gdays == green_day_diff:
                    gtype += "_green"
                elif green_day_diff < gdays and green_not_added:
                    json_data = {"day": green_dayEN, \
                                 "date": green_date.strftime(date_format), \
                                 "garbage": "green", \
                                 "diff": self._next_green_days}
                    json_data_list.append(json_data)
                    green_not_added = False

            json_data = {"day": dconverter(gday[i]), \
                         "date": gdate[i], \
                         "garbage": gtype, \
                         "diff": gdays}
            json_data_list.append(json_data)
    else:
      json_data = {}
      _LOGGER.debug("Fetch info for %s/%s/%s: %s", self._zipcode, self._publicplace, self._housenr, s)
      json_data_list.append(json_data)

    return json_data_list

class FKFGarbageCollectionSensor(Entity):

    def __init__(self, hass, name, zipcode, publicplace, housenr, offsetdays, calendar, calendar_lang, green, greencolor, ssl):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._zipcode = zipcode
        self._publicplace = "---".join(publicplace.rsplit(" ", 1)) if zipcode != ZIPCODE_BUDAORS else publicplace
        self._housenr = housenr
        self._state = None
        self._fkfdata = []
        self._current = "current"
        self._offsetdays = offsetdays
        self._icon = DEFAULT_ICON
        self._next_communal_days = None
        self._next_green_days = None
        self._next_selective_days = None
        self._calendar = calendar
        self._calendar_lang = calendar_lang
        self._green = green
        self._greencolor = greencolor
        self._ssl = ssl
        self._attr = {}

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
                 _LOGGER.debug("Creating fkfgarbage_collection calendar ")
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
    def extra_state_attributes(self):
        if 'diff' in self._fkfdata[0]:
          i = 0

          self._attr["items"] = len(self._fkfdata)

          while i < len(self._fkfdata):
            self._attr['in' + str(i)] = self._fkfdata[i]['diff']
            self._attr['day' + str(i)] = self._fkfdata[i]['day']
            self._attr['date' + str(i)] = self._fkfdata[i]['date']
            self._attr['garbage' + str(i)] = self._fkfdata[i]['garbage']
            i += 1

        self._attr["current"] = self._current
        self._attr["next_communal_days"] = self._next_communal_days
        self._attr["next_green_days"] = self._next_green_days
        self._attr["next_selective_days"] = self._next_selective_days
        self._attr["calendar_lang"] = self._calendar_lang

        self._attr["provider"] = CONF_ATTRIBUTION
        return self._attr

    def __repr__(self):
        """Return main sensor parameters."""
        return (
            f"FKFGarbagecollection[ name: {self._name}, "
            f"entity_id: {self.entity_id}, "
            f"state: {self.state}\n"
            f"config: {self.config}]"
        )

    async def async_update(self):
        self._next_communal_days = None
        self._next_green_days = None
        self._next_selective_days = None

        fkfdata = await async_get_fkfdata(self)

        if len(fkfdata) != 0:
           self._fkfdata = fkfdata
           self._state = min(int(200 if self._next_communal_days is None else self._next_communal_days), \
                             int(200 if self._next_green_days is None else self._next_green_days), \
                             int(200 if self._next_selective_days is None else self._next_selective_days))
           if self._state == 200:
               self._state = "unknown"
           self._current = "current"
        else:
           self._current = "false"
        return self._state

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if 'garbage' in self._fkfdata[0]:
            if self._fkfdata[0]['garbage'] == "communal":
                return DEFAULT_ICON
            elif self._fkfdata[0]['garbage'] == "green":
                return DEFAULT_ICON_GREEN
            else:
                return DEFAULT_ICON_SELECTIVE
        else:
            return DEFAULT_ICON
