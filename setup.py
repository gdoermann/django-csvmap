from setuptools import setup, find_packages

VERSION = (0, 1, 0)

# Dynamically calculate the version based on VERSION tuple
if len(VERSION)>2 and VERSION[2] is not None:
    str_version = "%d.%d_%s" % VERSION[:3]
else:
    str_version = "%d.%d" % VERSION[:2]

version= str_version

setup(
    name = 'django-csvmap',
    version = version,
    description = "django csv mapping",
    long_description = """This is a generic mapping protocol for saving and loading from csv""",
    author = 'Greg Doermann',
    author_email = 'gdoermann@snirk.com',
    url = 'http://github.com/gdoermann/django-csvmap',
    license = 'GNU General Public License',
    platforms = ['any'],
    classifiers = ['Development Status :: 3 - Alpha',
                   'Environment :: Web Environment',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GNU General Public License (GPL)',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Framework :: Django'],
    packages = find_packages(),
    include_package_data = True,
)