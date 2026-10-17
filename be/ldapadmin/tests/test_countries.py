import unittest

from be.ldapadmin import countries


class LoadCountriesTest(unittest.TestCase):

    def test_countries_from_package(self):
        data = countries.load_countries()
        self.assertEqual(len(data), 29)
        self.assertEqual(countries.get_country('GR')['pub_code'], 'EL')
        self.assertEqual(countries.get_country('ro')['name'], 'Romania')
        self.assertEqual(countries.get_country('eu')['pub_code'], 'EU')
        self.assertEqual(countries.get_country('gb')['pub_code'], 'UK')

    def test_unknown_country(self):
        countries.load_countries()
        self.assertEqual(countries.get_country('no')['name'], '')
