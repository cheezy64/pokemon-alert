import os
import time
import requests
import math
import signal

from retrying import retry
from fake_useragent import UserAgent
from pattern import HoneycombSearchPattern
from multiprocessing.dummy import Pool as ThreadPool
from pokemon import Pokemon, PokemonEncounter
from db.pokedex import Pokedex
from fake_useragent import UserAgent

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

FPM_DIAMETER = 400
TIMEOUT = 120

class FPMWebdriverAgent():
	
	def __init__(self, result_consumers):
		self._consumers = result_consumers

	def search(self, spot, loops_num):
		lat, lng = spot
		dests = HoneycombSearchPattern(lat, lng, loops_num, FPM_DIAMETER).get_destinations()

		driver = self.open_fpm()
		for spot in dests:
			try:
				result = self._search(driver, spot)
				for consumer in self._consumers:
					consumer.consume(result)
			except Exception as e:
				print str(e)
				print 'Erro ao procurar pokemon no  FPM, recuperando...'
		
		driver.quit()

	def open_fpm(self):
		options = Options()
		prefs = { "profile.default_content_setting_values.geolocation" : 2 }
		options.add_experimental_option("prefs", prefs)

		driver = webdriver.Chrome(chrome_options=options)
		driver.maximize_window()

		return driver

	@retry(stop_max_attempt_number=10)
	def _search(self, driver, spot):
		driver.get('https://fastpokemap.se/#%s,%s' % spot)
		driver.refresh()
		WebDriverWait(driver, TIMEOUT).until(
			EC.element_to_be_clickable((By.CLASS_NAME, 'close')))
		driver.find_element_by_class_name('close').click()
		WebDriverWait(driver, TIMEOUT).until(
			EC.element_to_be_clickable((By.CLASS_NAME, 'scan')))
		driver.find_element_by_class_name('scan').click()
		WebDriverWait(driver, TIMEOUT).until(
			EC.invisibility_of_element_located((By.CLASS_NAME, 'active')))

		elements = driver.find_elements_by_class_name('displaypokemon')
		return FPMSearchResult(elements)


class FPMSearchResult():

	def __init__(self, elements):
		self._elements = elements

	def pokemon(self):
		if not self._elements:
			return []

		pokedex = Pokedex()
		encounters = []
		for element in self._elements:
			try:
				id = element.get_attribute('data-pokeid')
				lat = element.get_attribute('data-lat')
				lng = element.get_attribute('data-lng')
				name = pokedex.name(id)
				expiration_ts = element.find_element_by_class_name('remainingtext').get_attribute('data-expire')
			except Exception, e:
				print 'pokemon disappears...'
				continue

			expiration = float(expiration_ts) / 1000
			spawn = ''
			encounter_id = ''

			pokemon = Pokemon(id, name)
			encounters.append(PokemonEncounter(pokemon, lat, lng, expiration, spawn, encounter_id))

		return encounters
