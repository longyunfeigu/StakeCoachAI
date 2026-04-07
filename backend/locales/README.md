Place compiled translation files under this folder.

Structure:

locales/
  en/LC_MESSAGES/messages.po|mo
  zh_Hans/LC_MESSAGES/messages.po|mo

Use Babel to extract and compile translations:

- Extract: pybabel extract -F babel.cfg -o locales/messages.pot .
- Init:    pybabel init -i locales/messages.pot -d locales -l en
- Init:    pybabel init -i locales/messages.pot -d locales -l zh_Hans
- Update:  pybabel update -i locales/messages.pot -d locales
- Compile: pybabel compile -d locales
