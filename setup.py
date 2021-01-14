''' be.ldapadmin installer '''
from setuptools import setup, find_packages

setup(name='be.ldapadmin',
      version='0.1',
      author='Eau de Web',
      author_email='office@eaudeweb.ro',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'naaya.ldapdump',
          'python-ldap',
          'colander',
          'BeautifulSoup',
          'lxml',
          'deform',
          'phonenumbers',
          'jellyfish==0.2.0',
          'xlrd>=0.9.3',
          'xlwt',
          'unidecode',
          'requests',
          'sparql-client',
          'python-dateutil',
          'pyDNS',
          'transliterate',
          'validate-email>=edw.1.3.1',
      ],
      entry_points={
          'console_scripts':
              [
                  'dump_ldap = be.ldapadmin.ldapdump:dump_ldap'
              ]
      },
      )
