''' be.ldapadmin installer '''
from setuptools import setup, find_namespace_packages

setup(name='be.ldapadmin',
      version='1.4.dev0',
      author='Eau de Web',
      author_email='office@eaudeweb.ro',
      packages=find_namespace_packages(include=['be.*']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'naaya.ldapdump >= 2.0.0',
          'python-ldap',
          'colander',
          'lxml',
          'deform',
          'phonenumbers',
          'jellyfish >= 1.0',
          'openpyxl',
          'xlsxwriter>=2.0.0',
          'unidecode',
          'requests',
          'python-dateutil',
          'transliterate',
      ],
      entry_points={
          'console_scripts':
              [
                  'dump_ldap = be.ldapadmin.ldapdump:dump_ldap'
              ]
      },
      )
